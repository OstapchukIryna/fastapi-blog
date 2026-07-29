from typing import Annotated

import bcrypt
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
    status,
)
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import models
from database import get_db
from routers.posts import posts_query
from schemas import (
    PostResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db)]


# --- Helpers ---------------------------------------------------------
async def current_author(db: AsyncSession) -> models.User:
    """
    Get author of current post.

    Args:
        db (AsyncSession): current database session

    Raises:
        HTTPException: If no author is found in the database, raises a 500 Internal Server Error with a message to run the seed script.

    Returns:
        models.User: The first user found in the database, representing the author of the current post.

    """
    result = await db.execute(select(models.User).order_by(models.User.id))
    author = result.scalars().first()
    if author is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No author in the database. Run: uv run python seed.py",
        )
    return author


# --- Dependencies ------------------------------------------------------
# Create dependencies for loading users from the database.
# These dependencies will be used in the route handlers to fetch the required data based on the provided parameters.
# Prevent code duplication and ensure consistent error handling for missing resources.
async def load_user(user_id: int, db: DbSession) -> models.User:
    """Returns user by id, otherwise 404."""
    user = await db.get(models.User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return user


UserDep = Annotated[models.User, Depends(load_user)]

# --- Routes ---------------------------------------------------------


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(user: UserCreate, db: DbSession):
    result = await db.execute(
        select(models.User).where(
            (models.User.username == user.username) | (models.User.email == user.email)
        )
    )
    clash = result.scalars().first()

    if clash is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered",
        )

    new_user = models.User(
        username=user.username,
        email=user.email,
        password_hash=bcrypt.hashpw(user.password.encode(), bcrypt.gensalt()).decode(),
    )
    db.add(new_user)
    try:
        await db.commit()
    except IntegrityError:
        # Race prevention
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered",
        ) from None
    return new_user


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user: UserDep):
    return user


@router.get("/{user_id}/posts", response_model=list[PostResponse])
async def get_user_posts(user: UserDep, db: DbSession):
    result = await db.execute(posts_query().where(models.Post.user_id == user.id))
    return result.scalars().unique().all()


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user_fields(
    user: UserDep, data: UserUpdate, db: DbSession
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

    The password never reaches the model as-is. The column is
    password_hash, so assigning `password` would set an attribute
    SQLAlchemy does not map — the request would report success and
    change nothing.

    Args:
        user (UserDep): the user being changed, resolved by the
            dependency, which raises 404 when it does not exist.
        data (UserUpdate): the fields to change, already validated.
        db (DbSession): current database session.

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
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username or email already registered",
            )

    if "password" in changes:
        user.password_hash = bcrypt.hashpw(
            changes.pop("password").encode(), bcrypt.gensalt()
        ).decode()

    for name, value in changes.items():
        setattr(user, name, value)

    try:
        await db.commit()
    except IntegrityError:
        # The same race create_user guards: two requests can both pass
        # the check above and collide at the unique index.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered",
        ) from None

    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user: UserDep, db: DbSession) -> Response:
    """Cascading deletion of a user. All posts will be delete as well. Returns an empty 204."""
    await db.delete(user)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
