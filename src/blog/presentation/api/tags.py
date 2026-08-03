from fastapi import APIRouter

from blog.infrastructure.database import DbSession
from blog.schemas import Page, PageParams, PostResponse, TagCount
from blog.services import posts, tags

router = APIRouter()


@router.get("", response_model=Page[TagCount])
async def list_tags(db: DbSession, page: PageParams):
    rows, total = await tags.with_counts(db, page)
    return Page[TagCount].of(
        ({"name": name, "count": count} for name, count in rows), total, page
    )


@router.get("/{tag}/posts", response_model=Page[PostResponse])
async def get_tag_posts(tag: str, db: DbSession, page: PageParams):
    # 404 приходит из сервиса и только когда тега нет вовсе. Пустая
    # четвёртая порция у тега с тридцатью постами — это 200.
    items, total = await posts.with_tag(db, tag, page)
    return Page[PostResponse].of(items, total, page)
