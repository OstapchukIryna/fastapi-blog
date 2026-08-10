"""Who is currently talking to the application, and how they proved it.

core/security.py can check a signature and knows nothing about the
database. This module adds the database: a token becomes a row in the
users table rather than a number. The refusal lives here too, so a route
that declares CurrentUser never re-checks anything.

Signing in belongs here rather than with the account service: proving a
password, minting the token that then stands for it, and turning that
token back into a person are three steps of one story. They were in two
modules, and the pair of deliberately-identical refusals — an unknown
address and a wrong password must be indistinguishable — sat on either
side of the split, where nothing kept them in step.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from blog.core.config import settings
from blog.core.logging import user_id_var
from blog.core.security import (
    Unauthorized,
    create_access_token,
    verify_access_token,
    verify_password,
)
from blog.infrastructure import models
from blog.infrastructure.database import DbSession
from blog.schemas import Token

# The path is documentation as much as configuration: it is what the
# interactive docs put behind the Authorize button. Written out rather
# than built from API_PREFIX — services must not import presentation.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/token")

TokenDep = Annotated[str, Depends(oauth2_scheme)]


async def get_current_user(token: TokenDep, db: DbSession) -> models.User:
    """Resolve the bearer token to the account it names.

    Args:
        token (TokenDep): the bearer token, extracted from the header.
        db (DbSession): session to look the account up in.

    Returns:
        models.User: the signed-in account.

    Raises:
        Unauthorized: the token is unusable, or names an account that no
            longer exists. Both are 401 because in both cases the caller
            has to obtain a new token; the message differs only to help
            somebody debugging their own client.
    """
    # * int() collapses two refusals into one: a rejected token gives
    # * None, and a `sub` that is not a number gives whatever was in the
    # * claim. Neither is a user id, and neither deserves its own branch.
    try:
        # pyrefly: ignore [bad-argument-type]
        user_id = int(verify_access_token(token))
    except (TypeError, ValueError):
        raise Unauthorized("Invalid or expired token") from None

    user = await db.get(models.User, user_id)
    if not user:
        # Signed correctly, but the account has since been deleted.
        raise Unauthorized("User not found")

    # * Set once the account is known, not before — an anonymous or a
    # * rejected request should never appear to belong to somebody.
    user_id_var.set(user.id)
    return user


CurrentUser = Annotated[models.User, Depends(get_current_user)]


async def _register_failed_attempt(db: AsyncSession, user: models.User) -> None:
    """Count one more wrong password, and lock the account once too many pile up.

    The backoff doubles with every attempt past the threshold rather than
    resetting the clock to a fixed window, so a script that waits out one
    delay meets a longer one immediately after.

    Args:
        db (AsyncSession): session to write through.
        user (models.User): the account the attempt was against.
    """
    user.failed_login_attempts += 1
    if user.failed_login_attempts >= settings.login_lockout_threshold:
        backoff = settings.login_lockout_base_seconds * 2 ** (
            user.failed_login_attempts - settings.login_lockout_threshold
        )
        user.locked_until = datetime.now(UTC) + timedelta(seconds=backoff)
    await db.commit()


async def authenticate(db: AsyncSession, email: str, password: str) -> models.User:
    """The account these credentials belong to, or a 401.

    Which of the two was wrong is not said — that an account exists is
    itself something worth not telling an unauthenticated caller. A
    locked account is refused the same way, for the same reason: a
    different message here would tell a caller trying random passwords
    against random addresses which ones are real.

    Args:
        db (AsyncSession): session to look the account up in.
        email (str): the address as typed; matched case-insensitively,
            because that is how it is stored.
        password (str): the password as typed.

    Returns:
        models.User: the account, now known to be theirs.

    Raises:
        Unauthorized: the address is unknown, the account is locked out
            from too many recent failures, or the password is wrong.
    """
    result = await db.execute(
        select(models.User).where(func.lower(models.User.email) == email.lower())
    )
    user = result.scalars().first()

    if user is not None and user.locked_until is not None and user.locked_until > datetime.now(UTC):
        raise Unauthorized("Incorrect password or email")

    # ! One refusal for both cases, and no lookup that raises on its own.
    # ! A 404 for an unknown address and a 401 for a wrong password tells
    # ! anybody who asks whether a given email has an account here.
    if not user or not verify_password(password, user.password_hash):
        if user is not None:
            await _register_failed_attempt(db, user)
        raise Unauthorized("Incorrect password or email")

    if user.failed_login_attempts:
        user.failed_login_attempts = 0
        user.locked_until = None
        await db.commit()

    return user


def issue_token(user: models.User) -> Token:
    """Mint the token that stands for this account until it expires.

    Args:
        user (models.User): the account that has just proved itself.

    Returns:
        Token: the signed token and its type, shaped for the OAuth2
            password flow the interactive docs and the sign-in page use.
    """
    return Token(
        access_token=create_access_token(
            # * The subject is a string because JWT says so; turning it
            # * back into an int is get_current_user's problem.
            data={"sub": str(user.id)},
            expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
        ),
        token_type="bearer",
    )
