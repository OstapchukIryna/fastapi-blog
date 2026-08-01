from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.security import OAuth2PasswordRequestForm
from PIL import UnidentifiedImageError
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

import models
from auth import (
    CurrentUser,
    create_access_token,
    hash_password,
    verify_password,
)
from config import settings
from database import DbSession
from image_utils import delete_profile_image, process_profile_image
from routers.posts import posts_query
from schemas import PostResponse, Token, UserCreate, UserPrivate, UserPublic, UserUpdate

router = APIRouter()


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

# --- Routes ---------------------------------------------------------


@router.post("", response_model=UserPrivate, status_code=status.HTTP_201_CREATED)
async def create_user(user: UserCreate, db: DbSession):
    result = await db.execute(
        select(models.User).where(
            (func.lower(models.User.username) == user.username.lower())
            | (func.lower(models.User.email) == user.email.lower())
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
        email=user.email.lower(),
        password_hash=hash_password(user.password),
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


@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession
):
    # Look up user by case-**insensitive** email
    # NOTE: OAuth2PasswordRequestForm requires username field, but we treat it as email
    result = await db.execute(
        select(models.User).where(
            func.lower(models.User.email) == form_data.username.lower()
        )
    )
    user = result.scalars().first()

    # Verify user exists and password is correct
    # Don't reveal which one is failed if one was (security best practice)
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password or email",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token with user id as subject
    access_token_expires = timedelta(minutes=settings.accesse_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")


# Frontend get current user endpoint
@router.get("/me", response_model=UserPrivate)
async def get_current_user(current_user: CurrentUser):
    """Get the currently authenticated user"""
    return current_user


@router.get("/{user_id}", response_model=UserPublic)
def get_user(user: UserDep):
    return user


@router.get("/{user_id}/posts", response_model=list[PostResponse])
async def get_user_posts(user: UserDep, db: DbSession):
    result = await db.execute(posts_query().where(models.Post.user_id == user.id))
    return result.scalars().unique().all()


@router.patch("/{user_id}", response_model=UserPublic)
async def update_user_fields(
    user: OwnAccount, data: UserUpdate, db: DbSession
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
        if name.lower() in {"username", "email"} and value != getattr(user, name)
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
        user.password_hash = hash_password(changes.pop("password"))

    for name, value in changes.items():
        setattr(user, name, value.lower() if name == "email" else value)

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
async def delete_user(user: OwnAccount, db: DbSession):
    """Cascading deletion of a user. All posts will be delete as well as profile picture file"""
    old_filename = user.image_file
    await db.delete(user)
    await db.commit()

    if old_filename:
        delete_profile_image(old_filename)


@router.patch("/{user_id}/picture", response_model=UserPrivate)
async def upload_profile_picture(file: UploadFile, user: OwnAccount, db: DbSession):
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

    if old_filename:
        delete_profile_image(old_filename)

    return user


@router.delete("/{user_id}/picture", response_model=UserPrivate)
async def delete_profile_picture(user: OwnAccount, db: DbSession):
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
