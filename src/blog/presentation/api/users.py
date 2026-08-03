from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile, status
from fastapi.security import OAuth2PasswordRequestForm

from blog.core.config import settings
from blog.infrastructure.database import DbSession
from blog.schemas import (
    Token,
    UserCreate,
    UserPrivate,
    UserPublic,
    UserUpdate,
)
from blog.schemas.post import PaginatedPostResponse
from blog.services import auth, posts, users
from blog.services.auth import CurrentUser
from blog.services.posts import LimitDep, SkipDep
from blog.services.users import OwnAccount, UserDep

router = APIRouter()


@router.post("", response_model=UserPrivate, status_code=status.HTTP_201_CREATED)
async def create_user(data: UserCreate, db: DbSession):
    return await users.register(db, data)


@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession
):
    # NOTE: OAuth2PasswordRequestForm requires username field, but we treat it as email
    user = await users.authenticate(db, form_data.username, form_data.password)
    return auth.issue_token(user)


# Frontend get current user endpoint
@router.get("/me", response_model=UserPrivate)
async def get_current_user(current_user: CurrentUser):
    """Get the currently authenticated user"""
    return current_user


@router.get("/{user_id}", response_model=UserPublic)
def get_user(user: UserDep):
    return user


@router.get("/{user_id}/posts", response_model=PaginatedPostResponse)
async def get_user_posts(
    user: UserDep,
    db: DbSession,
    limit: LimitDep = 0,
    skip: SkipDep = settings.posts_per_page,
):
    return await posts.by_author(db, user.id, skip, limit)


@router.patch("/{user_id}", response_model=UserPublic)
async def update_user_fields(user: OwnAccount, data: UserUpdate, db: DbSession):
    return await users.apply_changes(db, user, data)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user: OwnAccount, db: DbSession):
    await users.delete(db, user)


@router.patch("/{user_id}/picture", response_model=UserPrivate)
async def upload_profile_picture(file: UploadFile, user: OwnAccount, db: DbSession):
    return await users.set_picture(db, user, file)


@router.delete("/{user_id}/picture", response_model=UserPrivate)
async def delete_profile_picture(user: OwnAccount, db: DbSession):
    return await users.clear_picture(db, user)
