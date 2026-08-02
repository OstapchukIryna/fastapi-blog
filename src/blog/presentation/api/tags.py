from fastapi import APIRouter

from blog.infrastructure.database import DbSession
from blog.schemas import PostResponse, TagCount
from blog.services import tags
from blog.services.posts import TaggedPostsDep

router = APIRouter()


@router.get("", response_model=list[TagCount])
async def list_tags(db: DbSession):
    return [
        {"name": name, "count": count} for name, count in await tags.with_counts(db)
    ]


@router.get("/{tag}/posts", response_model=list[PostResponse])
def get_tag_posts(posts: TaggedPostsDep):
    return posts
