"""JSON endpoints for posts.

The full set of verbs on one resource. Preconditions — the post exists,
the post is yours — are dependencies rather than lines in a body, so each
route reads as the single thing it is for.
"""

from fastapi import APIRouter, status

from blog.infrastructure import models
from blog.infrastructure.database import DbSession
from blog.schemas import (
    Page,
    PageParams,
    PostCreate,
    PostDetail,
    PostResponse,
    PostUpdate,
)
from blog.services import posts
from blog.services.auth import CurrentUser
from blog.services.posts import OwnedPost, PostDep

router = APIRouter()


@router.get("", response_model=Page[PostResponse])
async def list_posts(db: DbSession, page: PageParams) -> Page[PostResponse]:
    """Return one page of posts, newest first.

    Args:
        db (DbSession): request-scoped session.
        page (PageParams): skip and limit from the query string.

    Returns:
        Page[PostResponse]: the batch and what is needed to ask for more.
    """
    # * The envelope is built here rather than in the service, because a
    # * page needs the posts themselves, not their JSON representation.
    items, total = await posts.list_all(db, page)
    return Page[PostResponse].of(items, total, page)


@router.get("/{post_id}", response_model=PostDetail)
def get_post(post: PostDep) -> models.Post:
    """Return one post, including its body.

    Args:
        post (PostDep): resolved from the path; 404 if there is no such
            post, before this body runs.

    Returns:
        models.Post: the row. `response_model` above turns it into a
            PostDetail on the way out; annotating the wire shape here
            instead would be a claim the function does not honour.
    """
    return post


@router.post("", response_model=PostDetail, status_code=status.HTTP_201_CREATED)
async def create_post(form: PostCreate, current_user: CurrentUser, db: DbSession) -> models.Post:
    """Publish a new post under the caller's name.

    Args:
        form (PostCreate): the complete post.
        current_user (CurrentUser): the author, taken from the token
            rather than from the body — otherwise a caller could publish
            in somebody else's name.
        db (DbSession): request-scoped session.

    Returns:
        models.Post: the stored post.
    """
    return await posts.create(db, form, current_user)


@router.put("/{post_id}", response_model=PostDetail)
async def update_all_post_fields(post: OwnedPost, form: PostCreate, db: DbSession) -> models.Post:
    """Replace every editable field of a post.

    Args:
        post (OwnedPost): the post, already established to exist and to
            belong to the caller.
        form (PostCreate): the complete replacement. A field left out
            does not stay as it was — it takes the model's default.
        db (DbSession): request-scoped session.

    Returns:
        models.Post: the post as stored.
    """
    return await posts.replace(db, post, form)


@router.patch("/{post_id}", response_model=PostDetail)
async def update_post_fields(post: OwnedPost, changes: PostUpdate, db: DbSession) -> models.Post:
    """Change some fields of a post and leave the rest alone.

    Args:
        post (OwnedPost): the post, existing and owned.
        changes (PostUpdate): only the fields being changed.
        db (DbSession): request-scoped session.

    Returns:
        models.Post: the post as stored.
    """
    return await posts.update(db, post, changes)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(post: OwnedPost, db: DbSession) -> None:
    """Delete a post.

    Args:
        post (OwnedPost): the post, existing and owned.
        db (DbSession): request-scoped session.

    Returns:
        None: 204 with no body, from the decorator's status_code — there
            is nothing left to say once the post is gone. Repeating the
            request gives 404, because by then there is nothing at that
            id either.
    """
    await posts.delete(db, post)
