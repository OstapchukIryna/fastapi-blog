"""Passwords and the token protocol — and nothing else.

There is no session and no request here. These functions turn a password
into a hash, and a user id into a token and back. Whether that id belongs
to anyone is a question for services/auth.py, one layer up, because
answering it needs the database.
"""

from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException, status
from pwdlib import PasswordHash

from blog.core.config import settings

# * Argon2 only, chosen for us by pwdlib's "recommended" preset. Worth
# * knowing: this hasher does not recognise a bcrypt hash and raises on
# * one rather than answering "no match", so anything that writes to
# * users.password_hash must go through hash_password below.
password_hash = PasswordHash.recommended()


class Unauthorized(HTTPException):
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
                at the call sites — see services/users.authenticate.
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


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Sign a JWT carrying the given claims.

    Args:
        data (dict): claims to encode. The caller supplies `sub`; the
            expiry is added here so no caller can forget it.
        expires_delta (timedelta | None): how long the token should last.
            Defaults to the configured lifetime.

    Returns:
        str: the encoded token.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(
            minutes=settings.accesse_token_expire_minutes
        )

    to_encode.update({"exp": expire})
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
            acceptable. Still a string at this point: whether it names a
            real user is the next layer's question.
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
        return payload.get("sub")
