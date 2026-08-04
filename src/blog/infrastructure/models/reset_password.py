<<<<<<< HEAD
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from blog.infrastructure.database import Base
from blog.infrastructure.models.user import User


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
=======
"""One-time tokens for resetting a forgotten password."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from blog.infrastructure.database import Base

if TYPE_CHECKING:
    from blog.infrastructure.models.user import User

# sha256 hex is always 64 characters.
TOKEN_HASH_LENGTH = 64


class PasswordResetToken(Base):
    """A pending "I forgot my password" request.

    The token itself is never stored — only its sha256. Somebody who
    reads the database therefore cannot use what they find, which is the
    same reason passwords are not stored either. Unlike a password this
    one needs no slow hash: the value is 32 random bytes, so there is
    nothing to guess and nothing to brute-force.

    Rows are deleted rather than marked used. A token that has been spent
    and a token that never existed should be indistinguishable to the
    caller, and the simplest way to guarantee that is to have nothing
    left to distinguish.

    Attributes:
        id (int): surrogate primary key.
        user_id (int): whose request this is. Cascades, so deleting an
            account cannot leave a live token pointing at nothing.
        token_hash (str): sha256 of the token that was emailed. Unique,
            and the only column ever searched on.
        expires_at (datetime): when the token stops working.
        created_at (datetime): when it was issued.
        user (User): the account this resets.
    """

    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(
        String(TOKEN_HASH_LENGTH), unique=True, nullable=False
    )
>>>>>>> 922b4cf9e635a611cedb8890870a51f3197184e4
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

<<<<<<< HEAD
    user: Mapped[User] = relationship(back_populates="reset_token")
=======
    # * Imported for typing only. User names this class in its own
    # * relationship, so importing it back at runtime would be a cycle —
    # * and was: the application stopped starting with an ImportError
    # * naming a partially initialised module.
    user: Mapped[User] = relationship(back_populates="reset_tokens")

    @property
    def expired(self) -> bool:
        """Whether this token is past its expiry.

        SQLite has no timezone-aware column type, so a datetime read back
        from it arrives naive even though a timezone-aware one went in.
        Comparing that to an aware "now" raises rather than answering, so
        the stored value is labelled UTC on the way out — which is what
        it always was.

        Returns:
            bool: True when the token should no longer be accepted.
        """
        expires_at = self.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return expires_at < datetime.now(UTC)
>>>>>>> 922b4cf9e635a611cedb8890870a51f3197184e4
