"""
Посты: что про них можно спросить и что с ними можно сделать.

Транзакция принадлежит этому модулю, а не роуту: функция, которая
меняет пост, сама и коммитит. Иначе «сохранить» было бы двумя строками,
и рано или поздно одна из поверхностей забыла бы вторую.
"""

from collections.abc import Sequence
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import Select, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from blog.infrastructure import models
from blog.infrastructure.database import DbSession
from blog.schemas import PostForm, PostUpdate
from blog.services.auth import CurrentUser
from blog.services.tags import get_or_create_tags

# --- Queries ---------------------------------------------------------


def posts_query() -> Select[tuple[models.Post]]:
    """
    Build the base post query with its relations already loaded.

    selectinload and joinedload are not speculative optimisation: without
    them, touching post.tags in a template issues one query per post,
    which is the N+1 problem.

    Returns:
        Select: posts ordered newest first by date, with tags and author loaded.

    """
    return (
        select(models.Post)
        .options(
            selectinload(models.Post.tags),
            joinedload(models.Post.author),
        )
        .order_by(models.Post.date_posted.desc())
    )


async def all_posts(db: AsyncSession) -> Sequence[models.Post]:
    """Every post, newest first."""
    result = await db.execute(posts_query())
    return result.scalars().unique().all()


async def by_author(db: AsyncSession, user_id: int) -> Sequence[models.Post]:
    """Everything one person wrote, newest first."""
    result = await db.execute(posts_query().where(models.Post.user_id == user_id))
    return result.scalars().unique().all()


async def find_related(
    db: AsyncSession, current: models.Post, limit: int = 2
) -> tuple[list[dict], str]:
    """
    Find related posts by tags. Returns a list of related posts with shared tags.

    Args:
        db (AsyncSession): current database session
        current (models.Post): current post
        limit (int, optional): Limit of related posts to return. Defaults to 2.

    Returns:
        tuple[list[dict], str]: List of related posts with shared tags
        and a label indicating the type of relation

    """
    current_tags = {tag.name for tag in current.tags}

    if current_tags:
        result = await db.execute(
            posts_query()
            .join(models.Post.tags)
            .where(
                models.Tag.name.in_(current_tags),
                models.Post.id != current.id,
            )
        )

        candidates = result.scalars().unique().all()

        matched = [
            {"post": p, "shared": sorted(current_tags & {t.name for t in p.tags})}
            for p in candidates
        ]
        if matched:
            matched.sort(
                key=lambda m: (len(m["shared"]), m["post"].date_posted), reverse=True
            )
            return matched[:limit], "Related"

    result = await db.execute(
        posts_query().where(models.Post.id != current.id).limit(limit)
    )
    fallback = result.scalars().unique().all()
    return [{"post": p, "shared": []} for p in fallback], "More posts"


# --- Dependencies ------------------------------------------------------


async def load_post(post_id: int, db: DbSession) -> models.Post:
    """Returns post by id, otherwise 404."""
    result = await db.execute(posts_query().where(models.Post.id == post_id))
    post = result.scalars().first()
    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )
    return post


PostDep = Annotated[models.Post, Depends(load_post)]


def owned_post(post: PostDep, current_user: CurrentUser) -> models.Post:
    """
    The post at this id, once it is established that it is the caller's.

    A precondition rather than a step, so it is a dependency: the routes
    that change a post have nothing to say about somebody else's, and
    `post: OwnedPost` in the signature says both things at once — that
    the post exists, and that it is yours to change.

    Args:
        post (PostDep): the post, already loaded or already a 404.
        current_user (CurrentUser): whoever the token belongs to.

    Raises:
        HTTPException: 403 when the post belongs to somebody else. Not
            401 — the caller is known, they are simply not the author.

    Returns:
        models.Post: the same post, now known to be theirs.

    """
    if post.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorize to change this post",
        )
    return post


OwnedPost = Annotated[models.Post, Depends(owned_post)]


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


# --- Changes ---------------------------------------------------------


async def create(db: AsyncSession, data: PostForm, author: models.User) -> models.Post:
    """
    Store a new post by this author.

    The relationship wants the User, not its id — assigning the id here
    made SQLAlchemy try to treat an int as a User.
    """
    post = models.Post(
        title=data.title,
        summary=data.summary,
        content=data.content,
        author=author,
        tags=await get_or_create_tags(db, data.tags),
    )
    db.add(post)
    await db.commit()
    await db.refresh(post, attribute_names=["author"])
    return post


async def replace(db: AsyncSession, post: models.Post, data: PostForm) -> models.Post:
    """
    Replace every editable field of a post.

    PUT is a full replacement, so the body carries the whole post. Unlike
    apply_changes below, nothing is left alone: a field the client omits
    is not "unchanged", it becomes whatever PostForm defaults it to. That
    is why the dump has no exclude_unset — with it, PUT would quietly
    behave like PATCH and the two endpoints would be the same.

    Args:
        db (AsyncSession): current database session.
        post (models.Post): the post being replaced.
        data (PostForm): the complete replacement, already validated.

    Returns:
        models.Post: the post as stored after the replacement.

    """
    replacement = data.model_dump()
    post.tags = await get_or_create_tags(db, replacement.pop("tags"))
    for name, value in replacement.items():
        setattr(post, name, value)

    await db.commit()
    await db.refresh(post, attribute_names=["author"])
    return post


async def apply_changes(
    db: AsyncSession, post: models.Post, data: PostUpdate
) -> models.Post:
    """
    Change some fields of a post, leaving the rest alone.

    Which fields to touch comes from exclude_unset, so an omitted field
    and a field sent as null both mean "leave it alone". The keys can
    only be PostUpdate's own, which is what makes setattr safe here.

    Tags are replaced as a set rather than merged: sending [] clears
    them, omitting the key keeps them. There is no way to add one tag
    without naming the others, which is the usual trade for keeping a
    collection field simple.

    The author is not in the body — ownership is not editable. An empty
    body changes nothing and returns the post unchanged.

    Args:
        db (AsyncSession): current database session.
        post (models.Post): the post being changed.
        data (PostUpdate): the fields to change, already validated.

    Returns:
        models.Post: the post as stored after the change.

    """
    changes = data.model_dump(exclude_unset=True, exclude_none=True)

    if "tags" in changes:
        post.tags = await get_or_create_tags(db, changes.pop("tags"))
    for name, value in changes.items():
        setattr(post, name, value)

    await db.commit()
    return post


async def delete(db: AsyncSession, post: models.Post) -> None:
    """
    Delete a post.

    Asking again gives 404, not success: DELETE is idempotent in its
    effect — the post is gone either way — but the second call honestly
    reports that there was nothing at that id to delete.

    The rows in post_tags go with the post. The tags themselves stay,
    even when nothing references them any more; they are invisible in
    /api/tags, which joins through posts, but they do accumulate.
    """
    await db.delete(post)
    await db.commit()


async def set_pinned(db: AsyncSession, post: models.Post, *, pinned: bool) -> None:
    """
    Set pinned status for a post.

    At most one post is pinned, and nothing in the schema enforces it —
    the other rows are cleared here, in the same transaction.

    Args:
        db (AsyncSession): current database session
        post (models.Post): post to be pinned
        pinned (bool): if True, pin the post; if False, unpin the post

    """
    if pinned:
        await db.execute(
            update(models.Post)
            .where(models.Post.id != post.id, models.Post.is_pinned.is_(True))
            .values(is_pinned=False)
        )
    post.is_pinned = pinned
    await db.commit()
