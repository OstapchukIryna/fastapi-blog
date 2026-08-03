"""The shapes data takes at the edge of the application.

One module per entity, as in the models and for the same reason: it stays
visible who refers to whom. Post knows about User, because a post
response embeds its author, and about the tag rules. Nothing refers back.

`pagination` refers to nobody at all, which is exactly what let it break
the cycle between the posts and tags services — a slice is not a property
of either entity, so it belongs at the boundary.
"""

from blog.schemas.pagination import Page, PageParams, Pagination
from blog.schemas.post import (
    PostCreate,
    PostDetail,
    PostForm,
    PostFormInput,
    PostResponse,
    PostUpdate,
)
from blog.schemas.tag import TagCount, normalise_tags
from blog.schemas.user import (
    Token,
    UserBase,
    UserCreate,
    UserPrivate,
    UserPublic,
    UserUpdate,
)

__all__ = [
    "Page",
    "PageParams",
    "Pagination",
    "PostCreate",
    "PostDetail",
    "PostForm",
    "PostFormInput",
    "PostResponse",
    "PostUpdate",
    "TagCount",
    "Token",
    "UserBase",
    "UserCreate",
    "UserPrivate",
    "UserPublic",
    "UserUpdate",
    "normalise_tags",
]
