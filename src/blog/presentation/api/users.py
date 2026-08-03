from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile, status
from fastapi.security import OAuth2PasswordRequestForm

from blog.infrastructure.database import DbSession
from blog.schemas import (
    Page,
    PageParams,
    PostResponse,
    Token,
    UserCreate,
    UserPrivate,
    UserPublic,
    UserUpdate,
)
from blog.services import auth, posts, users
from blog.services.auth import CurrentUser
from blog.services.users import OwnAccount, UserDep

router = APIRouter()


@router.post("", response_model=UserPrivate, status_code=status.HTTP_201_CREATED)
async def create_user(registration: UserCreate, db: DbSession):
    return await users.register(db, registration)


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


@router.get("/{user_id}/posts", response_model=Page[PostResponse])
async def get_user_posts(user: UserDep, db: DbSession, page: PageParams):
    items, total = await posts.for_author(db, user.id, page)
    return Page[PostResponse].of(items, total, page)


@router.patch("/{user_id}", response_model=UserPublic)
async def update_user_fields(user: OwnAccount, changes: UserUpdate, db: DbSession):
    return await users.update(db, user, changes)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user: OwnAccount, db: DbSession):
    await users.delete(db, user)


@router.patch("/{user_id}/picture", response_model=UserPrivate)
async def upload_profile_picture(file: UploadFile, user: OwnAccount, db: DbSession):
    return await users.set_picture(db, user, file)


@router.delete("/{user_id}/picture", response_model=UserPrivate)
async def delete_profile_picture(user: OwnAccount, db: DbSession):
    return await users.remove_picture(db, user)
