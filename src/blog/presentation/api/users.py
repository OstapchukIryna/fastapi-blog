"""JSON endpoints for accounts: registration, sign-in, profile, picture.

Two dependencies carry the whole authorisation story. `UserDep` means the
account exists; `OwnAccount` means it exists and it is the caller's. Every
route that changes something asks for the second, so no route body checks
who is calling.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile, status
from fastapi.security import OAuth2PasswordRequestForm

from blog.infrastructure import models
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
async def create_user(registration: UserCreate, db: DbSession) -> models.User:
    """Register an account.

    Args:
        registration (UserCreate): handle, email and password.
        db (DbSession): request-scoped session.

    Returns:
        models.User: the row. `response_model` above narrows it to
            UserPrivate on the way out — including the email, which the
            caller has just supplied, so returning it reveals nothing.

    Raises:
        HTTPException: 400 when the handle or the email is taken. Which
            of the two is never said: answering that would tell anyone
            who asks whether a given address has an account here.
    """
    return await users.register(db, registration)


@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession
) -> Token:
    """Exchange credentials for a bearer token.

    Args:
        form_data (OAuth2PasswordRequestForm): the standard OAuth2
            password form. Its field is called `username` because the
            specification says so; this application puts the email there.
        db (DbSession): request-scoped session.

    Returns:
        Token: the signed token and its type.

    Raises:
        Unauthorized: the email is unknown or the password is wrong. One
            message for both, deliberately.
    """
    user = await users.authenticate(db, form_data.username, form_data.password)
    return auth.issue_token(user)


@router.get("/me", response_model=UserPrivate)
async def get_current_user(current_user: CurrentUser) -> models.User:
    """Return the account the caller's token belongs to.

    The page that shows a profile has no other way to find out: the token
    lives in localStorage, where the server cannot see it.

    Args:
        current_user (CurrentUser): resolved from the token.

    Returns:
        models.User: the caller's own account.
    """
    return current_user


@router.get("/{user_id}", response_model=UserPublic)
def get_user(user: UserDep) -> models.User:
    """Return an account as anybody may see it.

    Args:
        user (UserDep): resolved from the path; 404 if unknown.

    Returns:
        models.User: the row; the response model drops the email.
    """
    return user


@router.get("/{user_id}/posts", response_model=Page[PostResponse])
async def get_user_posts(
    user: UserDep, db: DbSession, page: PageParams
) -> Page[PostResponse]:
    """Return one page of what this person wrote.

    Args:
        user (UserDep): the author, resolved from the path.
        db (DbSession): request-scoped session.
        page (PageParams): skip and limit from the query string.

    Returns:
        Page[PostResponse]: the batch, with a total counting this
            author's posts rather than every post there is.
    """
    items, total = await posts.for_author(db, user.id, page)
    return Page[PostResponse].of(items, total, page)


@router.patch("/{user_id}", response_model=UserPublic)
async def update_user_fields(
    user: OwnAccount, changes: UserUpdate, db: DbSession
) -> models.User:
    """Change some fields of the caller's own account.

    Args:
        user (OwnAccount): the account, established to be the caller's.
        changes (UserUpdate): only the fields being changed.
        db (DbSession): request-scoped session.

    Returns:
        models.User: the account as stored.

    Raises:
        HTTPException: 400 when the requested handle or email already
            belongs to somebody else.
    """
    return await users.update(db, user, changes)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user: OwnAccount, db: DbSession) -> None:
    """Delete the caller's own account, and everything it wrote.

    Args:
        user (OwnAccount): the account, established to be the caller's.
        db (DbSession): request-scoped session.
    """
    await users.delete(db, user)


@router.patch("/{user_id}/picture", response_model=UserPrivate)
async def upload_profile_picture(
    file: UploadFile, user: OwnAccount, db: DbSession
) -> models.User:
    """Replace the caller's profile picture.

    Args:
        file (UploadFile): the uploaded image, in any format Pillow
            reads. It is normalised to a square JPEG before storage.
        user (OwnAccount): the account, established to be the caller's.
        db (DbSession): request-scoped session.

    Returns:
        models.User: the account, with the new image path.

    Raises:
        HTTPException: 400 when the upload is over the size ceiling or
            is not an image at all.
    """
    return await users.set_picture(db, user, file)


@router.delete("/{user_id}/picture", response_model=UserPrivate)
async def delete_profile_picture(user: OwnAccount, db: DbSession) -> models.User:
    """Drop the caller's picture and fall back to the shared default.

    Args:
        user (OwnAccount): the account, established to be the caller's.
        db (DbSession): request-scoped session.

    Returns:
        models.User: the account, now pointing at the default avatar.

    Raises:
        HTTPException: 400 when there was no picture to remove. Not 404:
            the account exists, the request simply asks for something
            that has already happened.
    """
    return await users.remove_picture(db, user)
