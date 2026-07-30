from collections.abc import Sequence
from dataclasses import dataclass, field
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
from database import get_db
from models import get_or_create_tags
from schemas import (
    PostCreate,
    PostDetail,
    PostFormInput,
    PostResponse,
    PostUpdate,
)

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db)]

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


def arrange(items: Sequence[models.Post]) -> dict:
    """
    Separate posts onto one pinned and others

    Args:
        items (Sequence[models.Post]): sequence of posts

    Returns:
        dict: Dictionary containing pinned post, lead post, and the rest of the posts

    """
    pinned = next((p for p in items if p.is_pinned), None)
    rest = [
        p for p in items if p is not pinned
    ]  # we need pop method and cannot use generator
    lead = pinned or (rest.pop(0) if rest else None)
    return {"pinned": pinned, "lead": lead, "rest": rest}


@dataclass(slots=True)
class PostFormView:
    """
    State of the post form, from which the page is drawn.

    Prevents passing too much arguments in functions and routs

    Three fields instead of the previous six arguments. Two of the old
    ones are derived rather than passed: editing means "there is a post",
    and 422 means "there are errors". Before, `mode="edit"` with
    `post=None`, or errors alongside a 200, were both constructible and
    nothing prevented it.

    Attributes:
        values (PostFormInput): what the person typed. Returned to the
            fields even when the post was not saved, so typed text is
            never lost.
        post (models.Post | None): the post being edited, or None when
            creating a new one.
        errors (dict[str, str]): field name to message, one per field.

    """

    values: PostFormInput
    post: models.Post | None = None
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def editing(self) -> bool:
        # Whether an existing post is being edited. Distinguishes editing from creating.
        return self.post is not None

    @property
    def title(self) -> str:
        # Title for the page and the browser tab.
        return "Edit post" if self.editing else "New post"

    @property
    def status_code(self) -> int:
        # HTTP status the form should be returned with.
        return (
            status.HTTP_422_UNPROCESSABLE_CONTENT if self.errors else status.HTTP_200_OK
        )


def post_to_input(post: models.Post) -> PostFormInput:
    # Convert an existing post that is being edited into the values its form fields show.
    return PostFormInput(
        title=post.title,
        summary=post.summary,
        content=post.content,
        tags=", ".join(tag.name for tag in post.tags),
    )


# --- Dependencies ------------------------------------------------------
# Create dependencies for loading posts from the database.
# These dependencies will be used in the route handlers to fetch the required data based on the provided parameters.
# Prevent code duplication and ensure consistent error handling for missing resources.


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

# --- Routes ---------------------------------------------------------


@router.get("", response_model=list[PostResponse])
async def list_posts(db: DbSession):
    # List all posts
    result = await db.execute(posts_query())
    return result.scalars().unique().all()


@router.get("/{post_id}", response_model=PostDetail)
# Show one post
def get_post(post: PostDep):
    return post


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post_api(post: PostDep, db: DbSession) -> Response:
    """
    Delete a post.

    Returns 204 with no body: there is nothing meaningful to send back
    about a resource that no longer exists.

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
        Response: an empty 204.

    """
    await db.delete(post)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("", response_model=PostDetail, status_code=status.HTTP_201_CREATED)
async def create_post(post: PostCreate, db: DbSession):
    # The only 404 check left in the route: the author comes in the request body,
    # not in the path, and the dependency on the path parameter will not see it.
    if await db.get(models.User, post.user_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    new_post = models.Post(
        title=post.title,
        summary=post.summary,
        content=post.content,
        user_id=post.user_id,
        tags=await get_or_create_tags(db, post.tags),
    )
    db.add(new_post)
    await db.commit()
    await db.refresh(new_post, attribute_names=["author"])
    return new_post


@router.put("/{post_id}", response_model=PostDetail)
async def update_all_post_fields(
    post: PostDep, data: PostCreate, db: DbSession
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
    if await db.get(models.User, data.user_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    replacement = data.model_dump()
    post.tags = await get_or_create_tags(db, replacement.pop("tags"))
    for name, value in replacement.items():
        setattr(post, name, value)

    await db.commit()
    await db.refresh(post, attribute_names=["author"])
    return post


@router.patch("/{post_id}", response_model=PostDetail)
async def update_post_fields(
    post: PostDep, data: PostUpdate, db: DbSession
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
