from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash

import models
from config import settings
from database import DbSession

password_hash = PasswordHash.recommended()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/token")


def unauthorized(detail: str) -> HTTPException:
    """
    A 401 carrying the challenge header.

    Returned rather than raised, so the `raise` stays at the place that
    decided to refuse. WWW-Authenticate is what makes it a challenge and
    not just a status: without it the OAuth flow has nothing to answer.
    """
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


# --- Dependencies ------------------------------------------------------
TokenDep = Annotated[str, Depends(oauth2_scheme)]


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(
            minutes=settings.accesse_token_expire_minutes
        )

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.secret_key.get_secret_value(), algorithm=settings.algorithm
    )
    return encoded_jwt


def verify_access_token(token: str) -> str | None:
    """Verify a JWT access token and return the subject (user id) if valid"""
    try:
        payload = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=[settings.algorithm],
            options={"require": ["exp", "sub"]},
        )
    except jwt.InvalidTokenError:
        return None
    else:
        return payload.get("sub")


async def get_current_user(token: TokenDep, db: DbSession) -> models.User:
    """Get the currently authenticated user"""
    # int() covers both refusals at once: a rejected token gives None,
    # and a sub that is not a number gives whatever was in the claim.
    try:
        user_id = int(verify_access_token(token))
    except TypeError, ValueError:
        raise unauthorized("Invalid or expired token") from None

    user = await db.get(models.User, user_id)
    if not user:
        raise unauthorized("User not found")
    return user


CurrentUser = Annotated[models.User, Depends(get_current_user)]
