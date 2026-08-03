"""
Authentication and authorization.
- --- IGNORE ---

core/security.py умеет проверить подпись и не знает про базу; здесь к
этому добавляется база — токен превращается в строку таблицы users, а не
в число. Отказ живёт тут же: роут, объявивший CurrentUser, ничего не
перепроверяет.
"""

from datetime import timedelta
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from blog.core.config import settings
from blog.core.security import create_access_token, unauthorized, verify_access_token
from blog.infrastructure import models
from blog.infrastructure.database import DbSession
from blog.schemas import Token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/token")

TokenDep = Annotated[str, Depends(oauth2_scheme)]


async def get_current_user(token: TokenDep, db: DbSession) -> models.User:
    """Get the currently authenticated user"""
    # int() covers both refusals at once: a rejected token gives None,
    # and a sub that is not a number gives whatever was in the claim.
    try:
        # pyrefly: ignore [bad-argument-type]
        user_id = int(verify_access_token(token))
    except TypeError, ValueError:
        raise unauthorized("Invalid or expired token") from None

    user = await db.get(models.User, user_id)
    if not user:
        raise unauthorized("User not found")
    return user


CurrentUser = Annotated[models.User, Depends(get_current_user)]


def issue_token(user: models.User) -> Token:
    """The token that stands for this user until it expires."""
    return Token(
        access_token=create_access_token(
            data={"sub": str(user.id)},
            expires_delta=timedelta(minutes=settings.accesse_token_expire_minutes),
        ),
        token_type="bearer",
    )
