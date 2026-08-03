"""Tags, and the table that ties them to posts."""

from typing import TYPE_CHECKING

from sqlalchemy import Column, ForeignKey, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from blog.infrastructure.database import Base

if TYPE_CHECKING:
    from blog.infrastructure.models.post import Post

# A plain table rather than a model: the association carries no data of
# its own, and nothing in the application ever needs to hold a row of it.
# Both sides cascade, so deleting a post or a tag removes the links
# without leaving rows pointing at nothing.
post_tags = Table(
    "post_tags",
    Base.metadata,
    Column("post_id", ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
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

    # * Post is imported for typing only: it imports this module for
    # * post_tags, so importing it back would be a cycle. The name is not
    # * defined at runtime and that is fine — since Python 3.14
    # * annotations are not evaluated when the class body runs (PEP 649),
    # * and SQLAlchemy resolves the name through its own registry.
    # * Verified with a standalone probe: no quotes, no runtime import,
    # * configure_mappers() passes.
    posts: Mapped[list[Post]] = relationship(secondary=post_tags, back_populates="tags")
