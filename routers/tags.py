from collections.abc import Sequence
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import models
from database import DbSession
from routers.posts import posts_query
from schemas import (
    PostResponse,
    TagCount,
)

router = APIRouter()


# --- Helpers ---------------------------------------------------------
async def all_topics(db: AsyncSession) -> list[tuple[str, int]]:
    """
    Sort tags by counting posts with them. Return list of tuples with tag name and count of posts.

    Args:
        db (AsyncSession): current database session

    Returns:
        list[tuple[str, int]]: List of tuples containing tag names and their respective post counts

    """
    result = await db.execute(
        select(models.Tag.name, func.count(models.Post.id))
        .join(models.Tag.posts)
        .group_by(models.Tag.id)
        .order_by(func.count(models.Post.id).desc(), models.Tag.name)
    )
    rows = result.all()
    return [(name, count) for name, count in rows]


# --- Dependencies ------------------------------------------------------
async def load_tagged_posts(tag: str, db: DbSession) -> Sequence[models.Post]:
    """Returns posts by tag, otherwise 404. If tags are not found or no posts with this tag, return 404."""
    result = await db.execute(
        posts_query().join(models.Post.tags).where(models.Tag.name == tag)
    )
    posts = result.scalars().unique().all()
    if not posts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found"
        )
    return posts


TaggedPostsDep = Annotated[Sequence[models.Post], Depends(load_tagged_posts)]


# --- Routes ---------------------------------------------------------


@router.get("", response_model=list[TagCount])
async def list_tags(db: DbSession):
    return [{"name": name, "count": count} for name, count in await all_topics(db)]


@router.get("/{tag}/posts", response_model=list[PostResponse])
def get_tag_posts(posts: TaggedPostsDep):
    return posts
