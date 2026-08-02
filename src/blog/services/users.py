"""
Учётные записи: регистрация, вход, профиль и картинка.

Файл на диске меняется здесь же, а не в роуте, и всегда после коммита:
если транзакция не прошла, старая картинка должна остаться на месте.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, UploadFile, status
from PIL import UnidentifiedImageError
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from blog.core.config import settings
from blog.core.security import hash_password, unauthorized, verify_password
from blog.infrastructure import models
from blog.infrastructure.database import DbSession
from blog.infrastructure.images import delete_profile_image, process_profile_image
from blog.schemas import UserCreate, UserUpdate
from blog.services.auth import CurrentUser


def already_registered() -> HTTPException:
    """
    The 400 for a username or email somebody already holds.

    Raised from three places — the check before the insert, and the
    unique index catching the two requests that both passed it — and the
    caller cannot be told which of the two fields clashed, because that
    would answer "is this person registered here" to anyone who asks.
    """
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Username or email already registered",
    )


# --- Dependencies ------------------------------------------------------


async def load_user(user_id: int, db: DbSession) -> models.User:
    """Returns user by id, otherwise 404."""
    user = await db.get(models.User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return user


UserDep = Annotated[models.User, Depends(load_user)]


def own_account(user: UserDep, current_user: CurrentUser) -> models.User:
    """
    The user at this id, once it is established that it is the caller.

    Args:
        user (UserDep): the account, already loaded or already a 404.
        current_user (CurrentUser): whoever the token belongs to.

    Raises:
        HTTPException: 403 when it is somebody else's account.

    Returns:
        models.User: the same account, now known to be theirs.

    """
    if user.id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorize to change profile",
        )
    return user


OwnAccount = Annotated[models.User, Depends(own_account)]


# --- Changes ---------------------------------------------------------


async def register(db: AsyncSession, data: UserCreate) -> models.User:
    """
    Create an account, or refuse because the name or the email is taken.

    Checked before the insert and again by the unique index: two requests
    can both pass the check and collide, and that race gives a 400 like
    any other clash rather than the 500 an IntegrityError would produce.
    """
    result = await db.execute(
        select(models.User).where(
            (func.lower(models.User.username) == data.username.lower())
            | (func.lower(models.User.email) == data.email.lower())
        )
    )
    if result.scalars().first() is not None:
        raise already_registered()

    user = models.User(
        username=data.username,
        email=data.email.lower(),
        password_hash=hash_password(data.password),
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        # Race prevention
        await db.rollback()
        raise already_registered() from None
    return user


async def authenticate(db: AsyncSession, email: str, password: str) -> models.User:
    """
    The user these credentials belong to, or a 401.

    Which of the two was wrong is not said — an account that exists is
    itself something worth not telling an unauthenticated caller.
    """
    # Look up user by case-**insensitive** email
    result = await db.execute(
        select(models.User).where(func.lower(models.User.email) == email.lower())
    )
    user = result.scalars().first()

    if not user or not verify_password(password, user.password_hash):
        raise unauthorized("Incorrect password or email")
    return user


async def apply_changes(
    db: AsyncSession, user: models.User, data: UserUpdate
) -> models.User:
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
        data (UserUpdate): the fields to change, already validated.

    Raises:
        HTTPException: 400 when the requested username or email already
            belongs to somebody else.

    Returns:
        models.User: the user as stored after the change.

    """
    changes = data.model_dump(exclude_unset=True, exclude_none=True)

    wanted = {
        name: value
        for name, value in changes.items()
        if name in {"username", "email"} and value != getattr(user, name)
    }
    if wanted:
        result = await db.execute(
            select(models.User).where(
                models.User.id != user.id,
                or_(*[getattr(models.User, n) == v for n, v in wanted.items()]),
            )
        )
        if result.scalars().first() is not None:
            raise already_registered()

    if "password" in changes:
        user.password_hash = hash_password(changes.pop("password"))

    for name, value in changes.items():
        setattr(user, name, value.lower() if name == "email" else value)

    try:
        await db.commit()
    except IntegrityError:
        # The same race register guards: two requests can both pass the
        # check above and collide at the unique index.
        await db.rollback()
        raise already_registered() from None

    return user


async def delete(db: AsyncSession, user: models.User) -> None:
    """Cascading deletion of a user. All posts will be delete as well as profile picture file"""
    old_filename = user.image_file
    await db.delete(user)
    await db.commit()

    delete_profile_image(old_filename)


async def set_picture(
    db: AsyncSession, user: models.User, file: UploadFile
) -> models.User:
    """
    Replace this user's profile picture, and drop the file it replaces.

    Pillow is synchronous and the resize is not free, so it runs in a
    worker thread rather than blocking the loop.

    Raises:
        HTTPException: 400 when the upload is over the size limit, or is
            not something Pillow recognises as an image.

    """
    content = await file.read()
    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File is too large. Maximum size is {settings.max_upload_size_bytes // (1024 * 1024)} MB",
        )
    try:
        new_filename = await run_in_threadpool(process_profile_image, content)
    except UnidentifiedImageError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image file. Please upload a valid file format (JPEG, PNG, GIF, WebP).",
        ) from err

    old_filename = user.image_file
    user.image_file = new_filename
    await db.commit()
    await db.refresh(user)

    delete_profile_image(old_filename)
    return user


async def clear_picture(db: AsyncSession, user: models.User) -> models.User:
    """Back to the shared default, and the uploaded file goes."""
    old_filename = user.image_file
    if old_filename is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No picture to delete.",
        )
    user.image_file = None
    await db.commit()
    await db.refresh(user)

    delete_profile_image(old_filename)
    return user
