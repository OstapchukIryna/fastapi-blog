"""Posts: what can be asked about them, and what can be done to them.

The dependencies that load a post and establish that it is yours live
here too, next to the queries they are built from.

The transaction belongs to this module rather than to the route: a
function that changes a post commits it. Otherwise "save" would be two
statements, and sooner or later one of the two surfaces would forget the
second one.

Listings return a pair — the records and the total — as ORM objects
rather than as a response schema. The envelope is assembled by whoever
asked: the JSON route wants Page[PostResponse], while a page wants the
posts themselves, because it reads outline and reading_minutes off them.
A service that returns the response shape can only serve one of the two,
and returning it is what broke the front page once.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import Select, func, select
from sqlalchemy import update as update_statement
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from blog.infrastructure import models
from blog.infrastructure.database import DbSession
from blog.schemas import PostForm, PostUpdate
from blog.schemas.pagination import Pagination
from blog.services import tags as tag_service
from blog.services.auth import CurrentUser

# --- Queries ---------------------------------------------------------


def base_query() -> Select[tuple[models.Post]]:
    """The query every listing starts from, relations already loaded.

    Eager loading is not speculative optimisation here, and it is not
    optimisation at all: under asyncio a lazy load raises MissingGreenlet
    rather than issuing the query it wants, because the attribute access
    that triggers it is synchronous and there is no way to await from
    inside it. On a synchronous stack the same access would quietly become
    one query per post — the N+1 problem. Either way the relations have to
    be loaded up front.

    Returns:
        Select: posts ordered pinned first, then newest, with their tags
            and authors attached.
    """
    # * Two strategies, because the two relations multiply differently.
    # * The author is many-to-one — one row per post — so joining costs
    # * nothing. Tags are a collection, and a JOIN repeats the whole post
    # * row once per tag, `content` included. Measured on 12 posts with 4
    # * tags each: joinedload ships 12 rows and 4.8 kB for a page of 3,
    # * selectinload ships 3 rows plus 12 tiny tag rows, 1.2 kB. The
    # * factor is the number of tags, and it is paid on the widest column
    # * in the table.
    #
    # ? An earlier version of this comment claimed joinedload would break
    # ? LIMIT here — that a page asking for ten would show four. It does
    # ? not: SQLAlchemy detects LIMIT with joined eager loading against a
    # ? collection and wraps the parent query in a subquery, so the limit
    # ? still counts posts. Verified — the SQL comes back as `FROM (SELECT
    # ? ... LIMIT ?) AS anon_1 LEFT OUTER JOIN ...` and returns exactly
    # ? three. The volume above is the real reason; the correctness
    # ? argument was wrong. What *does* break that way is an explicit
    # ? .join() — see the warning on _slice.
    #
    # * Pinned-first is decided in the query, not in the template. A
    # * template can only reorder what it was given, so on the second
    # * batch the pinned post is simply not in the slice: the hero spot
    # * would fall to whatever came first, and the pinned post would
    # * reappear later in date order. Sorting by id last makes the order
    # * total — without it, two posts sharing a second swap places
    # * between requests, and one shows up twice while another never
    # * shows up at all.
    return (
        select(models.Post)
        .options(
            selectinload(models.Post.tags),
            joinedload(models.Post.author),
        )
        .order_by(
            models.Post.is_pinned.desc(),
            models.Post.date_posted.desc(),
            models.Post.id.desc(),
        )
    )


async def _slice(
    db: AsyncSession, query: Select[tuple[models.Post]], page: Pagination
) -> tuple[Sequence[models.Post], int]:
    """Take one batch, and count how many exist under the same query.

    The count comes from the query that was passed in, not from the
    table: for an author's page the total is that author's posts, not
    every post there is. Counting the table instead leaves the "load
    more" button visible after the last record.

    Args:
        db (AsyncSession): session to query through.
        query (Select): the filtered, ordered query to take a batch from.
            ! It must return one row per post. See the warning below.
        page (Pagination): the offset and size being asked for.

    Returns:
        tuple[Sequence[models.Post], int]: the batch, and the total.
    """
    # ! The query handed in must not multiply rows, and nothing here can
    # ! check that. Eager loading is safe — SQLAlchemy wraps the parent
    # ! query in a subquery so LIMIT still counts posts. An explicit
    # ! .join() is not wrapped, because it was asked for and may be
    # ! load-bearing for the filter, so LIMIT counts join rows and
    # ! func.count() counts them too.
    # !
    # ! with_tag gets away with it: it joins the tags and filters on a
    # ! single name, so a post appears exactly once. Measured — asking for
    # ! three returns three. Widen that filter to `Tag.name.in_(...)` and
    # ! both numbers break at once: with four tags matching, a page of
    # ! three returned ONE post and the total read 48 for 12 posts.
    # ! Aggregate with a subquery or DISTINCT before slicing, not after.
    #
    # * order_by(None) before counting: sorting a subquery that is about
    # * to be reduced to a number is wasted work, and some databases
    # * reject it outright.
    total = await db.scalar(
        select(func.count()).select_from(query.order_by(None).subquery())
    )
    result = await db.execute(query.offset(page.skip).limit(page.limit))
    # * .unique() deduplicates in Python. Required rather than tidy:
    # * SQLAlchemy refuses a joined eager load against a collection
    # * without it (InvalidRequestError), and with_tag's explicit join can
    # * hand back the same post twice if the filter ever matches two tags.
    return result.scalars().unique().all(), total or 0


async def list_all(
    db: AsyncSession, page: Pagination
) -> tuple[Sequence[models.Post], int]:
    """One slice of every post, pinned first."""
    return await _slice(db, base_query(), page)


async def for_author(
    db: AsyncSession, author_id: int, page: Pagination
) -> tuple[Sequence[models.Post], int]:
    """One slice of what a person wrote."""
    return await _slice(db, base_query().where(models.Post.user_id == author_id), page)


async def with_tag(
    db: AsyncSession, tag: str, page: Pagination
) -> tuple[Sequence[models.Post], int]:
    """
    One slice of the posts carrying a tag.

    Raises:
        HTTPException: 404 when nothing anywhere carries this tag. Not
            when the slice is empty — page four of a tag with thirty
            posts is empty and perfectly found.

    """
    items, total = await _slice(
        db, base_query().join(models.Post.tags).where(models.Tag.name == tag), page
    )
    if total == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found"
        )
    return items, total


@dataclass(slots=True, frozen=True)
class Related:
    """One suggestion shown underneath a post, and the reason for it.

    Frozen because a suggestion is a computed result rather than state:
    it is built once per request and only ever read by the template.
    Making that explicit means a future caller cannot quietly patch a
    field and leave the rest of the object describing something else.

    Attributes:
        post (models.Post): the post being suggested.
        shared (list[str]): tag names the two posts have in common,
            sorted. Empty when the suggestion is a fallback rather than
            a real match, which is how the page tells the two apart.
    """

    post: models.Post
    shared: list[str]


async def find_related(
    db: AsyncSession, post: models.Post, limit: int = 2
) -> list[Related]:
    """Suggest a couple of posts to read after this one.

    Two strategies, in order of preference. Posts sharing at least one
    tag come first, ranked by how many tags they share and then by
    recency. When the post carries no tags, or nothing else uses them,
    the newest other posts stand in so the section is never empty.

    The caller distinguishes the two cases by looking at `shared`: a
    real match always has at least one tag in common, a fallback never
    does. Returning the heading text from here instead would put a
    piece of English in the service layer.

    Args:
        db (AsyncSession): session to query through.
        post (models.Post): the post currently being read.
        limit (int): how many suggestions to return at most.

    Returns:
        list[Related]: suggestions, best first. Empty only when this is
            the only post in the database.
    """
    own_tags = {tag.name for tag in post.tags}

    if own_tags:
        by_tag = await db.execute(
            base_query()
            .join(models.Post.tags)
            .where(models.Tag.name.in_(own_tags), models.Post.id != post.id)
        )
        matches = [
            Related(
                post=candidate,
                shared=sorted(own_tags & {t.name for t in candidate.tags}),
            )
            for candidate in by_tag.scalars().unique().all()
        ]
        if matches:
            # * Most tags in common wins; recency breaks the tie. reverse
            # * applies to both keys, which is what we want for each.
            matches.sort(
                key=lambda m: (len(m.shared), m.post.date_posted), reverse=True
            )
            return matches[:limit]

    newest = await db.execute(
        base_query().where(models.Post.id != post.id).limit(limit)
    )
    return [Related(post=other, shared=[]) for other in newest.scalars().unique().all()]


# --- Dependencies ------------------------------------------------------


async def load_post(post_id: int, db: DbSession) -> models.Post:
    """Load the post at this id, or refuse.

    A dependency rather than a helper, so that "this post exists" is
    established before a route body starts rather than inside it.

    Args:
        post_id (int): from the path.
        db (DbSession): session to load through.

    Returns:
        models.Post: the post, with tags and author already attached.

    Raises:
        HTTPException: 404 when no post has that id.
    """
    result = await db.execute(base_query().where(models.Post.id == post_id))
    post = result.scalars().first()
    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )
    return post


PostDep = Annotated[models.Post, Depends(load_post)]


def owned_post(post: PostDep, current_user: CurrentUser) -> models.Post:
    """The post at this id, once established to be the caller's.

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


# --- Changes ---------------------------------------------------------


async def create(db: AsyncSession, form: PostForm, author: models.User) -> models.Post:
    """Store a new post and return it as saved.

    Args:
        db (AsyncSession): session to write through.
        form (PostForm): the validated post.
        author (models.User): whoever the token belongs to. Passed as the
            object rather than an id — the relationship expects a User,
            and handing it an int makes SQLAlchemy try to treat the
            number as one.

    Returns:
        models.Post: the stored post, with its author refreshed so a
            response model can read it without a second query.
    """
    post = models.Post(
        title=form.title,
        summary=form.summary,
        content=form.content,
        author=author,
        tags=await tag_service.get_or_create(db, form.tags),
    )
    db.add(post)
    await db.commit()
    await db.refresh(post, attribute_names=["author"])
    return post


async def replace(db: AsyncSession, post: models.Post, form: PostForm) -> models.Post:
    """Replace every editable field of a post.

    PUT is a full replacement, so the body carries the whole post. Unlike
    update below, nothing is left alone: a field the client omits
    is not "unchanged", it becomes whatever PostForm defaults it to. That
    is why the dump has no exclude_unset — with it, PUT would quietly
    behave like PATCH and the two endpoints would be the same.

    Args:
        db (AsyncSession): current database session.
        post (models.Post): the post being replaced.
        form (PostForm): the complete replacement, already validated.

    Returns:
        models.Post: the post as stored after the replacement.
    """
    replacement = form.model_dump()
    post.tags = await tag_service.get_or_create(db, replacement.pop("tags"))
    for name, value in replacement.items():
        setattr(post, name, value)

    await db.commit()
    await db.refresh(post, attribute_names=["author"])
    return post


async def update(
    db: AsyncSession, post: models.Post, changes: PostUpdate
) -> models.Post:
    """Change some fields of a post, leaving the rest alone.

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
        changes (PostUpdate): the fields to change, already validated.

    Returns:
        models.Post: the post as stored after the change.
    """
    wanted = changes.model_dump(exclude_unset=True, exclude_none=True)

    if "tags" in wanted:
        post.tags = await tag_service.get_or_create(db, wanted.pop("tags"))
    for name, value in wanted.items():
        setattr(post, name, value)

    await db.commit()
    return post


async def delete(db: AsyncSession, post: models.Post) -> None:
    """Delete a post.

    Asking a second time gives 404 rather than success. DELETE is
    idempotent in its effect — the post is gone either way — but
    answering "done" for an id that holds nothing would be a claim about
    the world that is false.

    The rows in post_tags go with the post. The tags themselves stay,
    even once nothing references them; they are invisible in /api/tags,
    which counts through posts, but they do accumulate.

    Args:
        db (AsyncSession): session to write through.
        post (models.Post): the post to remove.
    """
    await db.delete(post)
    await db.commit()


async def set_pinned(db: AsyncSession, post: models.Post, *, pinned: bool) -> None:
    """Pin or unpin a post, keeping at most one pinned.

    The single-winner rule is enforced here rather than by a constraint,
    because clearing the previous winner and setting the new one has to
    happen in one transaction — a constraint could only reject the
    second write, not perform the first.

    Args:
        db (AsyncSession): session to write through.
        post (models.Post): the post to pin or unpin.
        pinned (bool): the state to leave it in. Keyword-only, so a call
            site cannot read as set_pinned(db, post, True) and leave the
            reader guessing what the boolean means.
    """
    if pinned:
        await db.execute(
            update_statement(models.Post)
            .where(models.Post.id != post.id, models.Post.is_pinned.is_(True))
            .values(is_pinned=False)
        )
    post.is_pinned = pinned
    await db.commit()
