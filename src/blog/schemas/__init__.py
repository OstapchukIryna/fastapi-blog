"""
The shapes data takes at the edge of the application.

Один модуль на сущность, как и в моделях, и по той же причине: видно,
кто на кого ссылается. Post знает про User (в ответе есть автор) и про
правила тегов; обратных ссылок нет. pagination не знает ни о ком —
поэтому и смог разорвать цикл между услугами постов и тегов.
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
