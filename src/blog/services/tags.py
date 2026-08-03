"""
Теги: пересчитать и создать недостающие.

Всё, что возвращает *посты* по тегу, лежит в services/posts.py — иначе
два модуля импортировали бы друг друга. Здесь только про сам тег.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from blog.infrastructure import models
from blog.services.posts import LimitDep, SkipDep


async def all_topics(
    db: AsyncSession, skip: SkipDep, limit: LimitDep
) -> list[tuple[str, int]]:
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
        .offset(skip)
        .limit(limit)
    )
    rows = result.all()
    return [(name, count) for name, count in rows]


async def get_or_create_tags(db: AsyncSession, names: list[str]) -> list[models.Tag]:
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
