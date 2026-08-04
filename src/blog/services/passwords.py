"""Everything about changing a password: forgotten, reset, or just changed.

Three routes' worth of rules, kept out of the routes. They shared enough
that written inline they came to three copies of the same refusal and
three copies of the same delete.

One rule runs through all of it: a caller learns nothing about who has an
account here. Asking to reset an unknown address answers exactly as it
answers a known one, and every way a token can be unusable produces the
same sentence.
"""

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from blog.core.config import settings
from blog.core.security import (
    generate_reset_token,
    hash_password,
    hash_reset_token,
    verify_password,
)
from blog.infrastructure import models


class InvalidResetToken(HTTPException):
    """The 400 for a reset token that cannot be used.

    One class, one message, for four different situations: no such token,
    already spent, expired, or the account it named has since been
    deleted. Telling them apart would let somebody holding a guess learn
    whether it was close.

    400 rather than 404: the address exists and the request was
    well-formed. What is wrong is the value inside it.
    """

    def __init__(self) -> None:
        """Build the refusal."""
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This reset link is invalid or has expired.",
        )


class WrongPassword(HTTPException):
    """The 400 for a change-password request that failed its own check.

    Distinct from the reset refusal on purpose: here the caller is
    already signed in, so nothing is revealed by saying which field was
    wrong, and saying so is the difference between a fixable mistake and
    a mystery.
    """

    def __init__(self) -> None:
        """Build the refusal."""
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )


async def _clear_tokens(db: AsyncSession, user_id: int) -> None:
    """Drop every outstanding reset token for one account.

    Called on issue, on use, and on an ordinary password change: in all
    three the tokens that existed a moment ago must stop working. Rows
    are removed rather than flagged, so a spent token and one that never
    existed look the same from outside.

    Args:
        db (AsyncSession): session to write through. Not committed here —
            the caller decides where the transaction ends.
        user_id (int): whose tokens to remove.
    """
    await db.execute(
        delete(models.PasswordResetToken).where(
            models.PasswordResetToken.user_id == user_id
        )
    )


async def start_reset(db: AsyncSession, email: str) -> tuple[models.User, str] | None:
    """Issue a reset token for this address, if it belongs to anybody.

    Returns None rather than raising for an unknown address, so the route
    can answer identically either way. Raising here is what turned the
    carefully neutral "if an account exists" message into a 404 that
    contradicted it.

    Args:
        db (AsyncSession): session to write through.
        email (str): the address as typed; matched case-insensitively.

    Returns:
        tuple[models.User, str] | None: the account and the token in the
            clear, ready to be emailed — or None when nobody holds this
            address. The token is returned rather than stored: the
            database only ever sees its hash.
    """
    found = await db.execute(
        select(models.User).where(func.lower(models.User.email) == email.lower())
    )
    user = found.scalars().first()
    if user is None:
        return None

    # * A new request invalidates the previous one. Two live links to the
    # * same account is one more than anybody needs, and the older one is
    # * the one more likely to have leaked.
    await _clear_tokens(db, user.id)

    token = generate_reset_token()
    db.add(
        models.PasswordResetToken(
            user_id=user.id,
            token_hash=hash_reset_token(token),
            expires_at=datetime.now(UTC)
            + timedelta(minutes=settings.reset_token_expire_minutes),
        )
    )
    await db.commit()
    return user, token


async def complete_reset(db: AsyncSession, token: str, new_password: str) -> None:
    """Set a new password using a token from an email.

    Args:
        db (AsyncSession): session to write through.
        token (str): the token as it arrived from the link.
        new_password (str): the replacement, already length-checked by
            the schema.

    Raises:
        InvalidResetToken: unknown, expired, or pointing at an account
            that no longer exists.
    """
    # * The whole row, not the token_hash column. Selecting the column
    # * returns a string, and `.expires_at` on a string is an
    # * AttributeError at request time — which is what happened, and what
    # * the type checker was silenced for saying.
    found = await db.execute(
        select(models.PasswordResetToken).where(
            models.PasswordResetToken.token_hash == hash_reset_token(token)
        )
    )
    reset_token = found.scalars().first()

    if reset_token is None:
        raise InvalidResetToken()

    if reset_token.expired:
        await db.delete(reset_token)
        await db.commit()
        raise InvalidResetToken()

    user = await db.get(models.User, reset_token.user_id)
    if user is None:
        raise InvalidResetToken()

    user.password_hash = hash_password(new_password)
    await _clear_tokens(db, user.id)
    await db.commit()


async def change(
    db: AsyncSession, user: models.User, current_password: str, new_password: str
) -> None:
    """Change the password of somebody who is already signed in.

    The current password is proved here, on the server. The profile page
    used to prove it by signing in with it a second time, because no
    endpoint accepted it — that workaround can go.

    Args:
        db (AsyncSession): session to write through.
        user (models.User): the account, already established as the
            caller's by the dependency.
        current_password (str): what they say their password is.
        new_password (str): the replacement.

    Raises:
        WrongPassword: the current password does not match.
    """
    if not verify_password(current_password, user.password_hash):
        raise WrongPassword()

    user.password_hash = hash_password(new_password)
    # A password change is also a statement that outstanding reset links
    # should stop working — often it is what somebody does *because* they
    # think one leaked.
    await _clear_tokens(db, user.id)
    await db.commit()
