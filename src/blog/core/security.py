"""
Пароли и протокол токена — и больше ничего.

Здесь нет ни сессии, ни запроса: функции превращают пароль в хеш, а id
пользователя в токен и обратно. Кому этот id принадлежит и существует ли
такой пользователь — вопрос services/auth.py, и он задаётся слоем выше.
"""

from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException, status
from pwdlib import PasswordHash

from blog.core.config import settings

password_hash = PasswordHash.recommended()


class Unauthorized(HTTPException):
    """
    A 401 carrying the challenge header.

    A class rather than a function returning one: `unauthorized(...)`
    read as a question about the caller, and the thing it returned was
    an object nobody could tell from a value. `raise Unauthorized(...)`
    says what it is, and the `raise` still stays at the place that
    decided to refuse.

    WWW-Authenticate is what makes it a challenge and not just a status:
    without it the OAuth flow has nothing to answer.
    """

    def __init__(self, detail: str) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


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
