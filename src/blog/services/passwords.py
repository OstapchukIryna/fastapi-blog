"""Everything about changing a password: forgotten, reset, or just changed.

Three routes' worth of rules, kept out of the routes. They shared enough
that written inline they came to three copies of the same refusal and
three copies of the same delete.

One rule runs through all of it: a caller learns nothing about who has an
account here. Asking to reset an unknown address answers exactly as it
answers a known one, and every way a token can be unusable produces the
same sentence.

That rule is why sending the email is arranged from here rather than from
the route. While the route held the `if issued is not None:`, the one
branch that must not be observable from outside was written on the surface
that answers — one early return away from being a way to test which
addresses have accounts. The route now calls one function and returns the
same sentence unconditionally, because there is nothing left for it to
decide.
"""

from datetime import UTC, datetime, timedelta
from typing import Protocol

from fastapi import status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from blog.core.config import settings
from blog.core.errors import AppHTTPError
from blog.core.security import (
    generate_reset_token,
    hash_password,
    hash_reset_token,
    verify_password,
)
from blog.infrastructure import models


class ResetMailer(Protocol):
    """Whatever can get a reset link to the person who asked for one.

    Deliberately narrow: an address, a name, a token, and no answer. This
    service has nothing to say about SMTP, about the wording of the
    message, or about *when* it goes out — that last one is a property of
    the response being sent, which only a route knows about.

    A Protocol rather than a Callable alias because the arguments are
    keyword-only, and `Callable[..., None]` cannot say that; a Protocol
    with `__call__` types the names as well as the shape. A Protocol
    rather than an ABC for the same reason as elsewhere: the
    implementation lives in presentation/, which this layer must not
    import, and structural typing means it does not have to import back.

    ! The body of `__call__` is its docstring and nothing else. `...`
    ! would be a statement that never runs, which coverage reports as a
    ! missed line for good.
    """

    def __call__(self, *, to_email: str, username: str, token: str) -> None:
        """Arrange for the link to reach this person.

        Failures are the implementation's business. There is nobody left
        to tell: the answer was deliberately the same whether or not an
        account exists, so it cannot now become "sending failed".

        Args:
            to_email (str): where to send it.
            username (str): how to address them.
            token (str): the one-time token, in the clear.
        """


class InvalidResetToken(AppHTTPError):
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


class WrongPassword(AppHTTPError):
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
        delete(models.PasswordResetToken).where(models.PasswordResetToken.user_id == user_id)
    )


async def request_reset(db: AsyncSession, email: str, mailer: ResetMailer) -> None:
    """Somebody has forgotten their password: do whatever that means.

    Everything the situation entails, in one function — find the account
    if there is one, invalidate the previous link, issue a new one, and
    hand it to something that will deliver it. Returns nothing at all,
    which is the point: there is no value a caller could branch on, so no
    caller can accidentally answer differently for an address that exists.

    Args:
        db (AsyncSession): session to write through.
        email (str): the address as typed; matched case-insensitively.
        mailer (ResetMailer): how the link gets delivered. Injected rather
            than imported, so this module knows that an email is sent and
            not how — and so a test can pass something that records the
            token instead of sending it.
    """
    issued = await _issue_token(db, email)
    if issued is None:
        # Nobody holds this address. The caller is told the same thing
        # either way, and there is nothing further to do.
        return

    user, token = issued
    mailer(to_email=user.email, username=user.username, token=token)


async def _issue_token(db: AsyncSession, email: str) -> tuple[models.User, str] | None:
    """Issue a reset token for this address, if it belongs to anybody.

    Returns None rather than raising for an unknown address, so the caller
    can carry on identically either way. Raising here is what turned the
    carefully neutral "if an account exists" message into a 404 that
    contradicted it.

    Args:
        db (AsyncSession): session to write through.
        email (str): the address as typed; matched case-insensitively.

    Returns:
        tuple[models.User, str] | None: the account and the token in the
            clear, ready to be emailed — or None when nobody holds this
            address, or when a request for it arrived within the last
            cooldown window. The token is returned rather than stored: the
            database only ever sees its hash.
    """
    found = await db.execute(
        select(models.User).where(func.lower(models.User.email) == email.lower())
    )
    user = found.scalars().first()
    if user is None:
        return None

    existing = await db.execute(
        select(models.PasswordResetToken).where(models.PasswordResetToken.user_id == user.id)
    )
    live_token = existing.scalars().first()
    cooldown_ends = datetime.now(UTC) - timedelta(seconds=settings.reset_token_cooldown_seconds)
    if live_token is not None and live_token.created_at > cooldown_ends:
        # * Somebody already has a live link on the way. Issuing a second
        # * one this soon cannot be the account owner checking their inbox
        # * again - it is either a slow mail server or somebody using this
        # * form to flood an address that is not theirs.
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
            expires_at=datetime.now(UTC) + timedelta(minutes=settings.reset_token_expire_minutes),
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
