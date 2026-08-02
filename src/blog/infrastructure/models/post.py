from datetime import UTC, datetime
from math import ceil

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from blog.infrastructure.database import Base
from blog.infrastructure.models.tag import Tag, post_tags
from blog.infrastructure.models.user import User


class Post(Base):
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
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )

    author: Mapped[User] = relationship(back_populates="posts")
    tags: Mapped[list[Tag]] = relationship(secondary=post_tags, back_populates="posts")

    @property
    def outline(self) -> list[str]:
        """Headers from post"""
        return [
            line.removeprefix("## ").strip()
            for line in self.content.splitlines()
            if line.startswith("## ")
        ]

    @property
    def reading_minutes(self) -> int:
        """Time to read based on resading speen 200 words per minutes, but min is one."""
        return max(1, ceil(len(self.content.split()) / 200))
