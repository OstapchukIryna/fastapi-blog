"""Accounts."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from blog.infrastructure.database import Base
from blog.infrastructure.images import AWSAvatars

if TYPE_CHECKING:
    from blog.infrastructure.models.post import Post
    from blog.infrastructure.models.reset_password import PasswordResetToken

DEFAULT_AVATAR = "/static/profile_pics/default.jpg"


class User(Base):
    """Someone who can sign in and write.

    Attributes:
        id (int): surrogate primary key, and the subject of the JWT.
        username (str): the public handle. Unique on lower(username), not
            on the raw column — a plain unique=True would let "alice" and
            "Alice" both exist, agreeing with services/users.py's
            case-insensitive check right up until that check is ever
            bypassed or a row is written some other way. The index makes
            the guarantee the schema's, not the caller's.
        email (str): stored lower-case on write, and unique on
            lower(email) for the same reason as username — belt as well
            as braces, since the lower-casing on write is what a caller
            could still skip.
        password_hash (str): Argon2 hash. Never the password.
        image_file (str | None): the stored avatar's filename, or None.
            Nullable and meaningful: None is "no picture of their own",
            not "unknown", and it is what image_path turns into the
            shared default.
        failed_login_attempts (int): consecutive wrong passwords since the
            last successful sign-in. Reset to 0 on success.
        locked_until (datetime | None): sign-in refuses everything until
            this passes, win or lose — set once failed_login_attempts
            crosses the threshold, and growing with each attempt after.
        password_changed_at (datetime | None): when the password was last
            reset or changed, or None if never. get_current_user compares
            this against a token's own `iat` and refuses one issued
            before it — otherwise a token minted before the owner reset
            their password because it leaked would keep working for
            whoever had it until it expired on its own.
        reset_tokens (list[PasswordResetToken]): outstanding "I forgot my
            password" requests. Deleted with the account.
        posts (list[Post]): everything this person wrote. Deleting the
            account deletes them — an orphaned post has no author to
            display and nothing to fall back to.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    image_file: Mapped[str | None] = mapped_column(String(200), default=None)
    failed_login_attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    # * Functional, not unique=True on the column: a plain unique index is
    # * case-sensitive, so it would let "alice" and "Alice" both exist
    # * even though every service-layer check compares through
    # * func.lower(). This is what makes that comparison an actual
    # * guarantee instead of a convention every caller has to remember.
    __table_args__ = (
        Index("ix_users_username_lower", func.lower(username), unique=True),
        Index("ix_users_email_lower", func.lower(email), unique=True),
    )

    posts: Mapped[list["Post"]] = relationship(
        back_populates="author",
        cascade="all, delete-orphan",
    )

    # Plural: a row per outstanding request. In practice there is at
    # most one, because issuing a new token clears the old ones — but
    # that is a rule the service keeps, not one the schema enforces.
    reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    @property
    def image_path(self) -> str:
        """The URL to show for this person, uploaded or default.

        Read-only on purpose: it is derived from image_file, and letting
        it be assigned would create a second place where the avatar lives
        and two ways for them to disagree. Changing the picture means
        changing image_file, which is what the service does.

        Delegated to AWSAvatars rather than built here: how a storage URL
        is shaped is exactly the knowledge that class exists to hold in
        one place, and a second copy of it here already went stale once —
        this docstring used to promise a path under /media, which nothing
        in the URL below has ever pointed at.

        Returns:
            str: the S3 URL for an uploaded picture, or the shared
                default under /static.
        """
        if self.image_file:
            return AWSAvatars().avatar_url(self.image_file)
        return DEFAULT_AVATAR
