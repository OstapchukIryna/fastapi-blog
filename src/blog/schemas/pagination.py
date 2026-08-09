"""A slice of a list: how one is asked for, and how one is handed back.

This is a module of its own rather than a couple of aliases living beside
posts, for a plain reason: tags are paged the same way. While the aliases
sat in services/posts.py, the tags service imported the posts service and
the posts service imported tags back, and the application stopped
importing at all.

A slice is not a property of any entity. It belongs at the boundary, so
both services read it from here and neither knows the other exists.
"""

from collections.abc import Iterable
from typing import Annotated, Any, Self

from fastapi import Query
from pydantic import BaseModel, Field, computed_field

from blog.core.config import settings

MAX_PAGE_SIZE = 100


class Pagination(BaseModel):
    """How much has already been shown, and how much to fetch next.

    skip and limit rather than page and size: the next batch arrives via
    a button on the same page rather than a jump to another one, and "how
    many are already on screen" is literally the offset. A page number
    would have to be kept somewhere else and multiplied back into an
    offset at every call site.

    Attributes:
        skip (int): records to pass over. Zero on a first visit.
        limit (int): how many to return. Defaults to the configured page
            size so the number lives in settings, not in four signatures.
    """

    skip: int = Field(default=0, ge=0, description="records to pass over")
    limit: int = Field(
        default=settings.posts_per_page,
        ge=1,
        le=MAX_PAGE_SIZE,
        description="how many entries to return in one page",
    )


# * A model behind Query() describes the query string the way a model
# * behind Form() describes a form and a model in the body describes
# * JSON. A route writes `page: PageParams` and receives numbers that
# * have already been checked.
PageParams = Annotated[Pagination, Query()]


class Page[T](BaseModel):
    """One batch of results, and what is needed to ask for the next.

    A single envelope for every list in the application: posts, an
    author's posts, posts under a tag, and the tags themselves. It
    replaced two identical classes with different field names, which had
    already started to drift.

    Generic so each use gets its own schema in the OpenAPI document: a
    client generating code from it sees a page of posts, not a page of
    anything.

    Attributes:
        items (list[T]): the records in this batch.
        total (int): how many exist under the same query — not in the
            table. An author's page counts that author's posts, which is
            what stops the "load more" button outliving the last one.
        skip (int): the offset this batch was taken at.
        limit (int): the size that was asked for. The batch may be
            shorter; it is never longer.
    """

    items: list[T]
    total: int
    skip: int
    limit: int

    @computed_field
    @property
    def has_more(self) -> bool:
        """Whether another batch exists after this one.

        Derived rather than stored, and derived here rather than at the
        four call sites that would otherwise each compute it. Off-by-one
        errors happen in the places where an expression was written a
        second time.

        Returns:
            bool: True when the end has not been reached.
        """
        return self.skip + len(self.items) < self.total

    @classmethod
    def of(cls, items: Iterable[Any], total: int, page: Pagination) -> Self:
        """Wrap what a service returned, keeping the request's own numbers.

        Call this on the parameterised class — `Page[PostResponse].of(…)`
        — so the ORM objects are validated into the response model right
        here. On the bare class the parameter is Any and anything at all
        would be accepted.

        Args:
            items (Iterable[Any]): the records, usually ORM rows.
            total (int): how many exist under the same query.
            page (Pagination): the slice that was requested; its skip and
                limit are echoed back so a client need not remember them.

        Returns:
            Self: the envelope, ready to be returned from a route.
        """
        return cls(items=list(items), total=total, skip=page.skip, limit=page.limit)
