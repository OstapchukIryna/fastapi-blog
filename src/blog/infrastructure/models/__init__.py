"""The ORM classes, one module per table.

This was a single models.py once, and it stayed readable only because
there are three entities. Splitting it was not about size but about the
direction of the references: it is now visible that Tag depends on
nobody, Post depends on both others, and User knows Post by name alone.

Import from here rather than from the submodules — `from
blog.infrastructure import models`, then `models.Post`. Doing so also
guarantees all three classes are registered before the first query:
SQLAlchemy resolves a relationship named in an annotation through its own
registry, and a class only reaches that registry when its module is
imported.
"""

from blog.infrastructure.models.post import Post
from blog.infrastructure.models.reset_password import PasswordResetToken
from blog.infrastructure.models.tag import Tag, post_tags
from blog.infrastructure.models.user import User

__all__ = ["PasswordResetToken", "Post", "Tag", "User", "post_tags"]
