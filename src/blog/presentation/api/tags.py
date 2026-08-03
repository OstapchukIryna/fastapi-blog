"""JSON endpoints for tags, and for the posts filed under one."""

from fastapi import APIRouter

from blog.infrastructure.database import DbSession
from blog.schemas import Page, PageParams, PostResponse, TagCount
from blog.services import posts, tags

router = APIRouter()


@router.get("", response_model=Page[TagCount])
async def list_tags(db: DbSession, page: PageParams) -> Page[TagCount]:
    """Return one page of tags with their post counts, most used first.

    Args:
        db (DbSession): request-scoped session.
        page (PageParams): skip and limit from the query string.

    Returns:
        Page[TagCount]: the batch of tags and the total.
    """
    rows, total = await tags.with_counts(db, page)
    return Page[TagCount].of(
        ({"name": name, "count": count} for name, count in rows), total, page
    )


@router.get("/{tag}/posts", response_model=Page[PostResponse])
async def get_tag_posts(
    tag: str, db: DbSession, page: PageParams
) -> Page[PostResponse]:
    """Return one page of the posts carrying a tag.

    Args:
        tag (str): the tag name, from the path.
        db (DbSession): request-scoped session.
        page (PageParams): skip and limit from the query string.

    Returns:
        Page[PostResponse]: the batch and the total for this tag.

    Raises:
        HTTPException: 404 when no post anywhere carries the tag. An
            empty fourth batch of a tag with thirty posts is a 200 — the
            address named something, it just has nothing left on it.
    """
    items, total = await posts.with_tag(db, tag, page)
    return Page[PostResponse].of(items, total, page)
