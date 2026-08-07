"""Tags, and the table that ties them to posts."""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from blog.infrastructure.database import Base

if TYPE_CHECKING:
    from blog.infrastructure.models.post import Post


class PostTag(Base):
    """Association table for the many-to-many relationship between posts and tags.

    Attributes:
        post_id (int): Foreign key to the posts table.
        tag_id (int): Foreign key to the tags table.
    """

    __tablename__ = "post_tags"

    post_id: Mapped[int] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[int] = mapped_column(
        ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )


class Tag(Base):
    """A label attached to any number of posts.

    Tags are created on demand when a post names them and are never
    deleted: removing the last post that used one leaves the row behind.
    It becomes invisible — every listing counts through posts — but it
    does accumulate, and it keeps holding its name against the unique
    index, so a later post reuses the same row rather than making a
    second one.

    Attributes:
        id (int): surrogate primary key.
        name (str): the tag itself, stored lower-case and stripped by the
            schema layer so "Python" and "python " cannot become two
            tags. Unique, and indexed because every tag page looks a post
            up by it.
        posts (list[Post]): posts carrying this tag.
    """

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(
        String(30), unique=True, nullable=False, index=True
    )

    posts: Mapped[list[Post]] = relationship(
        secondary="post_tags", back_populates="tags"
    )
