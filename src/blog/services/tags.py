"""
Теги: пересчитать и создать недостающие.

Всё, что возвращает *посты* по тегу, лежит в services/posts.py — иначе
два модуля импортировали бы друг друга. Здесь только про сам тег.

Срез приезжает из schemas/pagination.py, а не из услуги постов. Именно
на этом импорте и замкнулся круг: skip и limit не принадлежат постам.
"""

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from blog.infrastructure import models
from blog.schemas.pagination import Pagination


async def with_counts(
    db: AsyncSession, page: Pagination
) -> tuple[Sequence[tuple[str, int]], int]:
    """
    Теги с числом постов, самые частые сверху.

    «Всего» — это теги, у которых есть хотя бы один пост: соединение
    через посты отбрасывает осиротевшие, и считать их надо тем же
    способом, каким они отбираются, иначе кнопка «ещё» переживёт
    последнюю строку.

    Returns:
        tuple: строки (имя, число постов) и сколько таких строк всего.

    """
    counted = (
        select(models.Tag.name, func.count(models.Post.id).label("posts"))
        .join(models.Tag.posts)
        .group_by(models.Tag.id)
        .order_by(func.count(models.Post.id).desc(), models.Tag.name)
    )

    total = await db.scalar(
        select(func.count()).select_from(counted.order_by(None).subquery())
    )
    result = await db.execute(counted.offset(page.skip).limit(page.limit))
    return [(name, count) for name, count in result.all()], total or 0


async def get_or_create(db: AsyncSession, names: list[str]) -> list[models.Tag]:
    """Check of existing tags or create new ones."""
    if not names:
        return []
    result = await db.execute(select(models.Tag).where(models.Tag.name.in_(names)))
    existing = result.scalars().all()
    by_name = {tag.name: tag for tag in existing}

    for name in names:
        if name not in by_name:
            tag = models.Tag(name=name)
            db.add(tag)
            by_name[name] = tag

    return [by_name[name] for name in names]
