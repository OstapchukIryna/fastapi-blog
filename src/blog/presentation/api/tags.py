from fastapi import APIRouter

from blog.core.config import settings
from blog.infrastructure.database import DbSession
from blog.schemas import PostResponse
from blog.schemas.tag import PaginatedTagResponse
from blog.services import tags
from blog.services.posts import LimitDep, SkipDep, TaggedPostsDep

router = APIRouter()


@router.get("", response_model=PaginatedTagResponse)
async def list_tags(
    db: DbSession, skip: SkipDep = 0, limit: LimitDep = settings.posts_per_page
):
    return [
        {"name": name, "count": count}
        for name, count in await tags.all_topics(db, skip, limit)
    ]


@router.get("/{tag}/posts", response_model=list[PostResponse])
def get_tag_posts(posts: TaggedPostsDep):
    return posts
