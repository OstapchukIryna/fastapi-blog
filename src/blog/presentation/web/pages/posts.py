"""One post: reading it, writing it, editing it, deleting it.

The routes that end in a redirect rather than a page, together with the
article page itself. They are here and not with the listings because they
are the only pages on the site that *change* something, which is a
different set of concerns: a form that has to survive being wrong, a 303
so a refresh does not resubmit, and a precondition — the post exists —
established by a dependency before any body runs.

! Registration order matters inside this module. FastAPI matches in the
! order routes were added, so `/posts/new` has to be declared before
! `/posts/{post_id}` or "new" is parsed as a post id and answers 422.
"""

from typing import Annotated

from fastapi import APIRouter, Form, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from blog.infrastructure.database import DbSession
from blog.presentation.web.forms import (
    PostFormView,
    form_errors,
    post_to_input,
    render_post_form,
)
from blog.presentation.web.templating import templates
from blog.schemas import PostFormInput
from blog.services import posts
from blog.services.auth import CurrentUser
from blog.services.posts import OwnedPost, PostDep

router = APIRouter()


@router.get("/posts/new", name="new_post")
def new_post_form(request: Request) -> Response:
    """
    Show an empty form for a new post.

    Args:
        request (Request): needed by the template.

    Returns:
        Response: the blank form page.

    """
    return render_post_form(request, PostFormView(values=PostFormInput()))


@router.post("/posts/new", name="create_post_page")
async def create_post_page(
    request: Request,
    current_user: CurrentUser,
    db: DbSession,
    submitted: Annotated[PostFormInput, Form()],
) -> Response:
    """
    Create a post from the submitted form.

    FastAPI fills PostFormInput itself: a model behind Form() describes a
    form the way a model in the body describes JSON.

    Unreachable from a browser at the moment, and kept rather than deleted
    because that is a property of where the token lives, not of this
    route. A plain form POST carries no Authorization header, and the token
    sits in localStorage, so CurrentUser can never be satisfied here — the
    page's own script sends the fields to /api/posts instead. Moving the
    token into a cookie brings this path back with no change to the code
    below, which is why it stays.

    Args:
        request (Request): needed by the template and by url_for.
        current_user (CurrentUser): authorized current user.
        db (DbSession): current database session.
        submitted (PostFormInput): the fields as typed, unvalidated.

    Returns:
        Response: a 303 redirect to the new post, or the form again with
        errors and the typed text if validation failed.

    """
    try:
        form = submitted.validated()
    except ValidationError as exception:
        return render_post_form(
            request, PostFormView(values=submitted, errors=form_errors(exception))
        )

    post = await posts.create(db, form, current_user)
    return RedirectResponse(
        request.url_for("post_page", post_id=post.id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/posts/{post_id}/edit", name="edit_post")
def edit_post_form(request: Request, post: PostDep) -> Response:
    """
    Show the edit form filled with an existing post.

    Args:
        request (Request): needed by the template.
        post (PostDep): the post being edited, resolved by the
            dependency, which raises 404 when it does not exist.

    Returns:
        Response: the form page populated from the post.

    """
    return render_post_form(request, PostFormView(values=post_to_input(post), post=post))


@router.post("/posts/{post_id}/edit", name="update_post")
async def update_post(
    request: Request,
    post: OwnedPost,
    db: DbSession,
    submitted: Annotated[PostFormInput, Form()],
) -> Response:
    """
    Save an edit to a post.

    Unreachable from a browser for the same reason create_post_page is:
    a plain form POST carries no Authorization header, and OwnedPost
    needs one. The page's own script sends the fields to /api/posts/{id}
    instead - kept, not deleted, for when the token moves to a cookie.

    Args:
        request (Request): needed by the template and by url_for.
        post (OwnedPost): the post being edited, established as the
            caller's own.
        db (DbSession): current database session.
        submitted (PostFormInput): the fields as typed, unvalidated.

    Returns:
        Response: a 303 redirect to the post, or the form again with
        errors and the typed text if validation failed. The post is
        left untouched on failure, because the replacement happens after
        validation.

    """
    try:
        form = submitted.validated()
    except ValidationError as exception:
        return render_post_form(
            request,
            PostFormView(values=submitted, post=post, errors=form_errors(exception)),
        )

    await posts.replace(db, post, form)
    return RedirectResponse(
        request.url_for("post_page", post_id=post.id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/posts/{post_id}/delete", name="delete_post")
async def delete_post(post: OwnedPost, db: DbSession) -> Response:
    """Delete a post from the edit page and return to the front page.

    Unreachable from a browser for the same reason update_post is: the
    page's own script calls DELETE /api/posts/{id} instead. Kept here so
    the route is not missing if the token ever moves to a cookie.

    Args:
        post (OwnedPost): the post, established as the caller's own.
        db (DbSession): request-scoped session.

    Returns:
        Response: a 303 to the front page. There is nothing left to show
            at the post's own address.
    """
    await posts.delete(db, post)
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/posts/{post_id}", name="post_page")
async def post_page(request: Request, post: PostDep, db: DbSession) -> Response:
    """Render one post, with a couple of suggestions underneath.

    Args:
        request (Request): the request being answered.
        post (PostDep): the post, or a 404.
        db (DbSession): request-scoped session.

    Returns:
        Response: the rendered article page.
    """
    related = await posts.find_related(db, post)
    # * A real match always shares at least one tag; a fallback never does.
    heading = "Related" if related and related[0].shared else "More posts"
    return templates.TemplateResponse(
        request,
        "post.html",
        {
            "post": post,
            "related": related,
            "related_label": heading,
            "title": post.title,
        },
    )
