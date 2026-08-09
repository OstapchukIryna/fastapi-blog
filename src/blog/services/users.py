"""The account itself: create one, change it, delete it.

Signing in moved to services/auth.py, where the token it produces already
lived. Pictures moved to services/avatars.py, which owns the storage they
are kept in. What is left here is one subject — the row in `users`, and
the two unique columns on it that every change has to be checked against.

The dependencies that load an account and establish that it is the
caller's live here too, beside the row they load.
"""

from typing import Annotated

from fastapi import Depends, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from blog.core.errors import AppHTTPError, Forbidden, NotFound
from blog.core.security import hash_password
from blog.infrastructure import models
from blog.infrastructure.database import DbSession
from blog.infrastructure.images import AWSAvatars
from blog.schemas import UserCreate, UserUpdate
from blog.services.auth import CurrentUser


class AlreadyRegistered(AppHTTPError):
    """
    The 400 for a username or email somebody already holds.

    Raised from four places — the check before the insert, and the
    unique index catching the two requests that both passed it — and the
    caller cannot be told which of the two fields clashed, because that
    would answer "is this person registered here" to anyone who asks.
    """

    def __init__(self) -> None:
        """Build the refusal, with a message that names neither field."""
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered",
        )


# --- Dependencies ------------------------------------------------------


async def load_user(user_id: int, db: DbSession) -> models.User:
    """Returns user by id, otherwise 404."""
    user = await db.get(models.User, user_id)
    if user is None:
        raise NotFound("User")
    return user


UserDep = Annotated[models.User, Depends(load_user)]


def own_account(user: UserDep, current_user: CurrentUser) -> models.User:
    """
    The user at this id, once it is established that it is the caller.

    Args:
        user (UserDep): the account, already loaded or already a 404.
        current_user (CurrentUser): whoever the token belongs to.

    Raises:
        Forbidden: 403 when it is somebody else's account.

    Returns:
        models.User: the same account, now known to be theirs.

    """
    if user.id != current_user.id:
        raise Forbidden("Not authorized to edit profile")
    return user


OwnAccount = Annotated[models.User, Depends(own_account)]


# --- Changes ---------------------------------------------------------


async def register(db: AsyncSession, registration: UserCreate) -> models.User:
    """
    Create an account.

    Checked before the insert.
    """
    result = await db.execute(
        select(models.User).where(
            (func.lower(models.User.username) == registration.username.lower())
            | (func.lower(models.User.email) == registration.email.lower())
        )
    )
    if result.scalars().first() is not None:
        raise AlreadyRegistered()

    user = models.User(
        username=registration.username,
        email=registration.email.lower(),
        password_hash=hash_password(registration.password),
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        # Race prevention
        await db.rollback()
        raise AlreadyRegistered() from None
    return user


async def _already_taken(db: AsyncSession, user: models.User, wanted: dict[str, object]) -> bool:
    """Report whether another account already holds the requested name or email.

    Only the two unique columns are worth asking about, and only when
    the value is actually changing: re-sending the username you already
    have is not a clash with yourself, and treating it as one would make
    a no-op edit fail.

    Args:
        db (AsyncSession): session to query through.
        user (models.User): the account being edited, excluded from the search.
        wanted (dict[str, object]): the fields the caller asked to change.

    Returns:
        bool: True when at least one requested value is taken.
    """
    contested = {
        name: value
        for name, value in wanted.items()
        if name in {"username", "email"} and value != getattr(user, name)
    }
    if not contested:
        return False

    clash = await db.execute(
        select(models.User).where(
            models.User.id != user.id,
            or_(*[getattr(models.User, n) == v for n, v in contested.items()]),
        )
    )
    return clash.scalars().first() is not None


async def update(db: AsyncSession, user: models.User, changes: UserUpdate) -> models.User:
    """
    Change some fields of a user, leaving the rest alone.

    Which fields to touch comes from exclude_unset, so an omitted field
    and a field sent as null both mean "leave it alone". The keys can
    only be UserUpdate's own, which is what makes setattr safe here.

    username and email are unique, so a change to either is checked
    against the other rows before it is applied: a duplicate is a 400,
    not the 500 an IntegrityError would produce. Re-sending the value a
    field already holds is not a clash with yourself and passes through
    as a no-op.

    The password never reaches the model as-is.

    Args:
        db (AsyncSession): current database session.
        user (models.User): the user being changed.
        changes (UserUpdate): the fields to change, already validated.

    Raises:
        AlreadyRegistered: 400 when the requested username or email
            already belongs to somebody else.

    Returns:
        models.User: the user as stored after the change.

    """
    wanted_changes = changes.model_dump(exclude_unset=True, exclude_none=True)

    if await _already_taken(db, user, wanted_changes):
        raise AlreadyRegistered()

    if "password" in wanted_changes:
        user.password_hash = hash_password(wanted_changes.pop("password"))

    for name, value in wanted_changes.items():
        setattr(user, name, value.lower() if name == "email" else value)

    try:
        await db.commit()
    except IntegrityError:
        # The same race register guards: two requests can both pass the
        # check above and collide at the unique index.
        await db.rollback()
        raise AlreadyRegistered() from None

    return user


async def delete(db: AsyncSession, user: models.User, storage: AWSAvatars) -> None:
    """Delete an account, its posts, and the picture it had.

    The posts go by cascade, which the schema handles. The file does not:
    nothing in the database knows that a string in `image_file` names
    something on S3, so the account service has to say so — and say it
    after the commit, so a failed transaction cannot leave a live row
    pointing at a file that has been removed.

    Args:
        db (AsyncSession): session to write through.
        user (models.User): the account to remove.
        storage (AWSAvatars): where its picture is kept. Taken as an
            argument rather than imported: this module has an opinion about
            *when* the file goes, and none about where it lives.
    """
    old_filename = user.image_file
    await db.delete(user)
    await db.commit()

    await storage.delete_profile_picture(old_filename)
