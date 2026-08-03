"""Accounts."""

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from blog.infrastructure.database import Base

if TYPE_CHECKING:
    from blog.infrastructure.models.post import Post

DEFAULT_AVATAR = "/static/profile_pics/default.jpg"


class User(Base):
    """Someone who can sign in and write.

    Attributes:
        id (int): surrogate primary key, and the subject of the JWT.
        username (str): the public handle. Unique, and compared
            case-insensitively when registering so two accounts cannot
            differ only in capitals.
        email (str): stored lower-case, which is what makes the unique
            index a real constraint rather than one a different
            capitalisation can slip past.
        password_hash (str): Argon2 hash. Never the password.
        image_file (str | None): the stored avatar's filename, or None.
            Nullable and meaningful: None is "no picture of their own",
            not "unknown", and it is what image_path turns into the
            shared default.
        posts (list[Post]): everything this person wrote. Deleting the
            account deletes them — an orphaned post has no author to
            display and nothing to fall back to.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    image_file: Mapped[str | None] = mapped_column(String(200), default=None)

    posts: Mapped[list[Post]] = relationship(
        back_populates="author",
        # delete-orphan as well as delete: detaching a post from its
        # author would otherwise leave a row with a dangling user_id.
        cascade="all, delete-orphan",
    )

    @property
    def image_path(self) -> str:
        """The URL to show for this person, uploaded or default.

        Read-only on purpose: it is derived from image_file, and letting
        it be assigned would create a second place where the avatar lives
        and two ways for them to disagree. Changing the picture means
        changing image_file, which is what the service does.

        Returns:
            str: a path under /media for an uploaded picture, or the
                shared default under /static.
        """
        if self.image_file:
            return f"/media/profile_pics/{self.image_file}"
        return DEFAULT_AVATAR
