"""Passwords and the token protocols.

There is no session and no request here. These functions turn a password
into a hash, a user id into a token and back, and implement password
reset tokens. Whether that id belongs to anyone is a question for
services/auth.py, one layer up, because answering it needs the database.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import status
from pwdlib import PasswordHash

from blog.core.config import settings
from blog.core.errors import AppHTTPError

# * Argon2 only, chosen for us by pwdlib's "recommended" preset. Worth
# * knowing: this hasher does not recognise a bcrypt hash and raises on
# * one rather than answering "no match", so anything that writes to
# * users.password_hash must go through hash_password below.
password_hash = PasswordHash.recommended()


class Unauthorized(AppHTTPError):
    """A 401 that carries the authentication challenge with it.

    A class rather than a function returning an exception: the old
    `unauthorized(...)` read as a question about the caller, and what it
    returned was indistinguishable from a value until you reached the
    `raise` further down. `raise Unauthorized(...)` says what it is,
    while keeping the raise at the place that decided to refuse.

    WWW-Authenticate is what makes the response a challenge rather than
    just a status: without it, a client following the OAuth flow has
    nothing to answer.
    """

    def __init__(self, detail: str) -> None:
        """Build the refusal.

        Args:
            detail (str): what the caller is told. Kept vague on purpose
                at the call sites — see services/auth.authenticate.
        """
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


def hash_password(password: str) -> str:
    """Hash a plain password for storage.

    Args:
        password (str): the password as typed.

    Returns:
        str: the hash, including its algorithm and parameters, so a
            future change of settings can be detected per row.
    """
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a password against a stored hash.

    Args:
        plain_password (str): the password as typed.
        hashed_password (str): the hash read from the database.

    Returns:
        bool: whether they match.
    """
    return password_hash.verify(plain_password, hashed_password)


def generate_reset_token() -> str:
    """Generate a one-time password-reset token.

    Returns:
        str: 32 random bytes, URL-safe encoded, for the caller to email
            and to pass to hash_reset_token before it touches the database.
    """
    return secrets.token_urlsafe(32)


def hash_reset_token(token: str) -> str:
    """Hash a reset token for storage.

    The token travels in the clear — it goes out by email, the one
    channel this application does not control the security of — so the
    database holds only this hash, the same reasoning as password_hash
    above. sha256 rather than Argon2 here is not a shortcut: Argon2 is
    slow on purpose, to make guessing a low-entropy human password
    expensive, and this is 32 random bytes with nothing to guess. Fast
    hashing costs nothing extra and answers requests sooner.

    Args:
        token (str): the token as generated, before it is emailed.

    Returns:
        str: the hash stored in place of the token itself.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(data: dict[str, str], expires_delta: timedelta | None = None) -> str:
    """Sign a JWT carrying the given claims.

    Args:
        data (dict[str, str]): claims to encode. The caller supplies
            `sub`; the expiry is added here so no caller can forget it.
        expires_delta (timedelta | None): how long the token should last.
            Defaults to the configured lifetime.

    Returns:
        str: the encoded token.
    """
    to_encode: dict[str, str | datetime] = dict(data)
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode["exp"] = expire
    return jwt.encode(
        to_encode, settings.secret_key.get_secret_value(), algorithm=settings.algorithm
    )


def verify_access_token(token: str) -> str | None:
    """Check a token's signature and return the subject it names.

    Every way a token can be unacceptable — wrong signature, expired,
    missing claims, not a JWT at all — collapses into the same None. The
    caller has one refusal to make and does not benefit from knowing
    which of them happened; telling a client the difference would only
    help someone probing.

    Args:
        token (str): the bearer token as received.

    Returns:
        str | None: the `sub` claim, or None if the token is not
            acceptable. Still a string at this point, guaranteed twice
            over: PyJWT itself raises InvalidSubjectError (a subclass of
            InvalidTokenError, caught below) for a `sub` of any other
            JSON type, and the isinstance check restates that as our own
            contract rather than a behaviour borrowed silently from a
            dependency we do not control the changelog of. Whether the
            string names a real user is still the next layer's question.
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=[settings.algorithm],
            # * Reject a token that omits either claim instead of reading
            # * a missing expiry as "never expires".
            options={"require": ["exp", "sub"]},
        )
    except jwt.InvalidTokenError:
        return None
    else:
        sub = payload.get("sub")
        return sub if isinstance(sub, str) else None
