from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
    status,
)
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

import models
from auth import CurrentUser
from database import DbSession
from models import get_or_create_tags
from schemas import (
    PostCreate,
    PostDetail,
    PostResponse,
    PostUpdate,
)


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


router = APIRouter()

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

# --- Helpers ---------------------------------------------------------


def posts_query():
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


async def set_pinned(db: AsyncSession, post: models.Post, *, pinned: bool) -> None:
    """
    Set pinned status for a post

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


# --- Routes ---------------------------------------------------------


@router.get("", response_model=list[PostResponse])
async def list_posts(db: DbSession):
    # List all posts
    result = await db.execute(posts_query())
    return result.scalars().unique().all()


# Show one post
@router.get("/{post_id}", response_model=PostDetail)
def get_post(post: PostDep):
    return post


@router.post("", response_model=PostDetail, status_code=status.HTTP_201_CREATED)
async def create_post(post: PostCreate, current_user: CurrentUser, db: DbSession):
    # Now the route is protected by CurrentUser check

    new_post = models.Post(
        title=post.title,
        summary=post.summary,
        content=post.content,
        user_id=current_user.id,
        tags=await get_or_create_tags(db, post.tags),
    )
    db.add(new_post)
    await db.commit()
    await db.refresh(new_post, attribute_names=["author"])
    return new_post


@router.put("/{post_id}", response_model=PostDetail)
async def update_all_post_fields(
    post: OwnedPost, data: PostCreate, db: DbSession
) -> models.Post:
    """
    Replace every editable field of a post.

    PUT is a full replacement, so the body must carry the whole post.
    Unlike the PATCH below it, nothing is left alone: a field the client
    omits is not "unchanged", it becomes whatever PostCreate defaults it
    to. That is why the dump has no exclude_unset — with it, PUT would
    quietly behave like PATCH and the two endpoints would be the same.

    user_id is part of the body, so a PUT can hand the post to another
    author. That user has to exist. Checking the post's own author would
    prove nothing: it exists by definition, or the post would not have
    been found.

    Args:
        post (PostDep): the post being replaced; the dependency raises
            404 when the id does not exist.
        data (PostCreate): the complete replacement, already validated.
        db (DbSession): current database session.

    Raises:
        HTTPException: 404 when data.user_id names a user that does not
            exist.

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


@router.patch("/{post_id}", response_model=PostDetail)
async def update_post_fields(
    post: OwnedPost, data: PostUpdate, db: DbSession
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
        post (PostDep): the post being changed, resolved by the
            dependency, which raises 404 when it does not exist.
        data (PostUpdate): the fields to change, already validated.
        db (DbSession): current database session.

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


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post_api(post: OwnedPost, db: DbSession) -> Response:
    """
    Delete a post.

    Repeating the request gives 404, not 204. DELETE is idempotent in
    its effect — the post is gone either way — but the second call is
    honestly reporting that there was nothing at that id to delete.

    The rows in post_tags go with the post. The tags themselves stay,
    even when nothing references them any more; they are invisible in
    /api/tags, which joins through posts, but they do accumulate.

    Args:
        post (PostDep): the post to delete; the dependency raises 404
            when the id does not exist.
        db (DbSession): current database session.

    Returns:
        Response: 204 with no body.

    """
    await db.delete(post)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
