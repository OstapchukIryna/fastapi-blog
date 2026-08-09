"""Posts: the thing the whole application exists to show."""

from datetime import UTC, datetime
from math import ceil

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from blog.infrastructure.database import Base
from blog.infrastructure.models.tag import Tag
from blog.infrastructure.models.user import User

WORDS_PER_MINUTE = 200


class Post(Base):
    """One published article.

    Attributes:
        id (int): surrogate primary key.
        title (str): headline.
        summary (str): one or two sentences shown in listings. Stored
            rather than derived from the content: the first paragraph of
            an article is rarely a good standalone description.
        content (str): the body, as Markdown. Rendered to HTML at display
            time, not at write time, so a change to the renderer applies
            to everything already published.
        is_pinned (bool): whether this post leads the front page. At most
            one row should be true, and nothing in the schema enforces
            that — services.posts.set_pinned clears the others inside the
            same transaction, so the invariant lives in one function
            rather than in a constraint.
        user_id (int): author. Indexed because the author page filters on
            it, and cascading because a post without an author cannot be
            displayed.
        date_posted (datetime): publication time, timezone-aware and
            indexed. Every listing sorts by it.
        author (User): the person who wrote it.
        tags (list[Tag]): labels, replaced wholesale when a post is
            edited rather than merged.
    """

    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    summary: Mapped[str] = mapped_column(String(250), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    date_posted: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        # * A callable, not datetime.now(UTC). Calling it here would
        # * freeze the default at import time and stamp every post with
        # * the moment the process started.
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )
    # Python-side and SQL-side defaults
    likes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    author: Mapped[User] = relationship(back_populates="posts")
    tags: Mapped[list[Tag]] = relationship(secondary="post_tags", back_populates="posts")

    @property
    def reading_minutes(self) -> int:
        """Rough reading time, never less than one minute.

        A word count over an assumed reading speed. The number gives a
        hint about length. A more precise estimate would not change what
        a reader decides.

        Returns:
            int: minutes, rounded up.

        Examples:
            >>> Post(content="one two three").reading_minutes
            1
            >>> Post(content=" ".join(["word"] * 250)).reading_minutes
            2
        """
        return max(1, ceil(len(self.content.split()) / WORDS_PER_MINUTE))
