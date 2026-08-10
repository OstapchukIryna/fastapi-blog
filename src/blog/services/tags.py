"""Tags: count them, and create the ones a post names.

Anything that returns *posts* for a tag lives in services/posts.py.
Keeping it there is what stops these two modules importing each other.

The slice comes from schemas/pagination.py rather than from the posts
service. That import is exactly where the cycle closed once: skip and
limit are not a property of posts.
"""

from collections.abc import Sequence

from sqlalchemy import delete as delete_statement
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from blog.infrastructure import models
from blog.schemas.pagination import Pagination


async def with_counts(db: AsyncSession, page: Pagination) -> tuple[Sequence[tuple[str, int]], int]:
    """List tags with how many posts use each, most used first.

    Ties are broken by name so the order is fully determined. Without
    that, two tags with the same count could swap places between
    requests, and one would appear on two consecutive pages while
    another appeared on none.

    Args:
        db (AsyncSession): session to query through.
        page (Pagination): which slice to return.

    Returns:
        tuple[Sequence[tuple[str, int]], int]: the rows as (name, count)
            pairs, and how many such rows exist in total.
    """
    counted = (
        select(models.Tag.name, func.count(models.Post.id).label("posts"))
        # * The join is also the filter: a tag no post references drops
        # * out here. delete_if_orphaned is what keeps that case rare, not
        # * what makes it safe to skip filtering — a row can still sit
        # * between "last post let go of it" and the call that notices.
        .join(models.Tag.posts)
        .group_by(models.Tag.id)
        .order_by(func.count(models.Post.id).desc(), models.Tag.name)
    )

    # * Counted the same way the rows are selected. Counting the tags
    # * table instead would include orphans and leave the "load more"
    # * button visible after the last real row.
    total = await db.scalar(select(func.count()).select_from(counted.order_by(None).subquery()))
    result = await db.execute(counted.offset(page.skip).limit(page.limit))
    return [(name, count) for name, count in result.all()], total or 0


async def get_or_create(db: AsyncSession, names: list[str]) -> list[models.Tag]:
    """Return a Tag row for each name, creating the missing ones.

    Added to the session but not committed: the caller is in the middle
    of saving a post, and the tags belong to that same transaction. If
    the post fails to save, the tags it would have introduced go with it.

    Args:
        db (AsyncSession): session to query and stage through.
        names (list[str]): tag names, already cleaned by the schema.

    Returns:
        list[models.Tag]: rows in the order the names were given, so the
            author's emphasis survives the round trip.
    """
    if not names:
        return []

    result = await db.execute(select(models.Tag).where(models.Tag.name.in_(names)))
    by_name = {tag.name: tag for tag in result.scalars().all()}

    for name in names:
        if name not in by_name:
            tag = models.Tag(name=name)
            db.add(tag)
            by_name[name] = tag

    return [by_name[name] for name in names]


async def delete_if_orphaned(db: AsyncSession, candidates: Sequence[models.Tag]) -> None:
    """Delete any of these tags no post uses any more.

    Called with a post's old tags after it stops using some of them — on
    delete, on replace, on an edit that drops one — since that is the
    only moment a tag can become orphaned. Checking here rather than
    trusting the caller to know which ones were actually dropped: a tag
    still in use is simply found still in use and left alone, which is
    cheaper to write than working out the difference at every call site.

    One DELETE with a NOT EXISTS, not a SELECT-then-maybe-DELETE per
    candidate: two round trips per tag would leave a gap of their own
    between the two, the same shape of race as calling this after the
    post's own commit did — a concurrent request could attach a fresh
    post to a tag in between this deciding it was orphaned and the row
    actually going away. A single statement is one atomic decision at
    the database, not two round trips this session could be paused
    between, and it costs one query for eight candidate tags instead of
    up to sixteen.

    Call this before the post's own commit, not after: within one
    transaction, SQLAlchemy autoflushes pending changes ahead of a query
    that could be affected by them, so the NOT EXISTS below already sees
    this post's own dropped association rows without needing them
    committed first.

    Args:
        db (AsyncSession): session to delete through. Not committed here
            — the caller decides where the transaction ends, the same
            contract as _clear_tokens in services/passwords.py and
            get_or_create above.
        candidates (Sequence[models.Tag]): tags that used to label a
            post that no longer does, or still does — either is fine,
            a tag any post still names is simply not matched.
    """
    if not candidates:
        return
    await db.execute(
        delete_statement(models.Tag).where(
            models.Tag.id.in_([tag.id for tag in candidates]),
            ~models.Tag.posts.any(),
        )
    )
