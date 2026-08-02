"""
The shapes data takes at the edge of the application.

Один модуль на сущность, как и в моделях, и по той же причине: видно,
кто на кого ссылается. Post знает про User (в ответе есть автор) и про
правила тегов; обратных ссылок нет.
"""

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
