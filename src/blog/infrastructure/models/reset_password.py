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
    token_hash: Mapped[str] = mapped_column(String(TOKEN_HASH_LENGTH), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    user: Mapped["User"] = relationship(back_populates="reset_tokens")

    @property
    def expired(self) -> bool:
        """Whether this token is past its expiry.

        Returns:
            bool: True when the token should no longer be accepted.
        """
        return self.expires_at < datetime.now(UTC)
