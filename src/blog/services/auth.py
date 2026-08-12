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

import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from blog.core.config import settings
from blog.core.errors import Forbidden
from blog.core.logging import user_id_var
from blog.core.security import (
    Unauthorized,
    create_access_token,
    hash_password,
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
logger = logging.getLogger(__name__)

TokenDep = Annotated[str, Depends(oauth2_scheme)]

# * Hashed once at import, not per request: Argon2 takes tens of
# * milliseconds, and authenticate() spends it against this whenever
# * there is no real hash to check against, so an unknown address takes
# * the same time to refuse as a wrong password does. Without this, the
# * short-circuit in authenticate()'s `or` never calls verify_password at
# * all for an unknown address, and the two cases become distinguishable
# * by response time alone — the same information the identical message
# * was written to withhold.
DUMMY_HASH = hash_password("this hash exists only to spend the same time an account lookup would")


async def get_current_user(request: Request, token: TokenDep, db: DbSession) -> models.User:
    """Resolve the bearer token to the account it names.

    Args:
        token (TokenDep): the bearer token, extracted from the header.
        db (DbSession): session to look the account up in.

    Returns:
        models.User: the signed-in account.

    Raises:
        Unauthorized: the token is unusable, names an account that no
            longer exists, or was issued before the account's password
            was last changed. All but one are 401 because in both cases
            the caller has to obtain a new token; the message differs
            only to help somebody debugging their own client.
    """
    claims = verify_access_token(token)
    if claims is None:
        raise Unauthorized("Invalid or expired token")

    try:
        user_id = int(claims.sub)
    except ValueError:
        # A signature that checks out but names a sub that was never a
        # user id - not reachable through this application's own tokens,
        # only through one crafted by someone who has the signing key.
        raise Unauthorized("Invalid or expired token") from None

    user = await db.get(models.User, user_id)
    if user is None:
        # Signed correctly, but the account has since been deleted.
        raise Unauthorized("User not found")

    # * A reset or a change stamps this; a token minted before that
    # * moment was signed by the account's old password, and a person
    # * changing their password is very often doing it because that old
    # * one just leaked. Without this, that token would keep working
    # * until its own exp regardless of the reason the password changed.
    # * A direct comparison is safe here specifically because
    # * create_access_token encodes iat as a float: a naive comparison
    # * against an iat truncated to whole seconds would make a token
    # * minted a fraction of a second after the change indistinguishable
    # * from one minted a fraction before it, in whichever direction that
    # * truncation happened to round.
    if user.password_changed_at is not None and claims.issued_at < user.password_changed_at:
        raise Unauthorized("Invalid or expired token")

    # * Set once the account is known, not before — an anonymous or a
    # * rejected request should never appear to belong to somebody.
    user_id_var.set(user.id)

    request.scope["user_id"] = user.id
    logger.info("scope stamped: %s / id(scope)=%s", user.id, id(request.scope))
    return user


CurrentUser = Annotated[models.User, Depends(get_current_user)]


def owner_only(current_user: CurrentUser) -> models.User:
    """The caller, established to be the blog's owner.

    A dependency rather than a check inside a route body, matching
    owned_post and own_account: `user: Owner` in a signature says the
    caller is authenticated and entitled.

    Args:
        current_user (CurrentUser): whoever the token belongs to.

    Raises:
        Forbidden: 403 when the caller is not the owner. settings.is_owner
            already treats an unset OWNER_USER_ID as nobody holding the
            privilege, not everybody.

    Returns:
        models.User: the same account, now known to be the owner's.
    """
    if not settings.is_owner(current_user.id):
        raise Forbidden("Not authorized")
    return current_user


Owner = Annotated[models.User, Depends(owner_only)]


async def _register_failed_attempt(db: AsyncSession, user: models.User) -> None:
    """Count one more wrong password, and lock the account once too many pile up.

    The backoff doubles with every attempt past the threshold rather than
    resetting the clock to a fixed window. That growth only happens here,
    though, and this only runs once a request actually reaches the
    password check — authenticate() refuses everything for free while
    locked_until is still in the future, without calling this. A script
    that keeps hammering during that window gains nothing and loses
    nothing: attempts made while locked are not counted at all, so the
    backoff is exactly as long the next time it is checked as it was when
    it was set. It only grows again once a request arrives after
    locked_until has passed and is still wrong — not from waiting less,
    not from trying harder, only from one more genuine failure.

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

    The same reasoning applies to how long this takes, not only to what
    it says: verify_password always runs, against DUMMY_HASH when there
    is no real one, so an unknown address costs the same tens of
    milliseconds a wrong password against a real one does. A short-circuit
    that skipped hashing for an unknown address would leave the message
    identical while the response time was not — which is exactly the
    signal an address list gets built from.

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

    # ! One refusal for both cases, and no lookup that raises on its own.
    # ! A 404 for an unknown address and a 401 for a wrong password tells
    # ! anybody who asks whether a given email has an account here. Every
    # ! branch below calls verify_password before raising, on purpose: an
    # ! unknown address, a locked account, and a wrong password all spend
    # ! the same tens of milliseconds on Argon2. A wrong password against
    # ! a real account also earns a database round trip: _register_failed_attempt
    # ! writes and commits the failed count, something neither of the
    # ! other two branches does. That gap shows up on a local network and
    # ! buries itself in internet jitter. It stays open on purpose -
    # ! writing on every attempt, real or fake, would close it at a cost
    # ! the leak does not justify.
    if user is None:
        verify_password(password, DUMMY_HASH)
        raise Unauthorized("Incorrect password or email")

    locked = user.locked_until is not None and user.locked_until > datetime.now(UTC)
    password_ok = verify_password(password, user.password_hash)

    if locked or not password_ok:
        if not locked:
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
