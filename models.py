from datetime import UTC, datetime
from math import ceil

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    Table,
    Text,
    select,
)
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from database import Base

# many-to-many table without class
post_tags = Table(
    "post_tags",
    Base.metadata,
    Column("post_id", ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    image_file: Mapped[str | None] = mapped_column(String(200), default=None)

    posts: Mapped[list[Post]] = relationship(
        back_populates="author",
        cascade="all, delete-orphan",
    )

    @property
    def image_path(self) -> str:
        if self.image_file:
            return f"/media/profile_pics/{self.image_file}"
        return "/static/profile_pics/default.jpg"


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(
        String(30), unique=True, nullable=False, index=True
    )

    posts: Mapped[list[Post]] = relationship(secondary=post_tags, back_populates="tags")


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


def get_or_create_tags(db: Session, names: list[str]) -> list[Tag]:
    """Check of existing tags or create new ones."""
    if not names:
        return []

    existing = db.execute(select(Tag).where(Tag.name.in_(names))).scalars().all()
    by_name = {tag.name: tag for tag in existing}

    for name in names:
        if name not in by_name:
            tag = Tag(name=name)
            db.add(tag)
            by_name[name] = tag

    return [by_name[name] for name in names]
