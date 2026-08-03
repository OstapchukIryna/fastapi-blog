"""
The HTML side of the site: every page a useropens in a browser.

"""

from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Form, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from blog.core.config import settings
from blog.infrastructure import models
from blog.infrastructure.database import DbSession
from blog.presentation.web.forms import (
    PostFormView,
    form_errors,
    post_to_input,
    render_post_form,
)
from blog.presentation.web.templating import templates
from blog.schemas import PostFormInput
from blog.services import posts, tags
from blog.services.auth import CurrentUser
from blog.services.posts import (
    LimitDep,
    PostDep,
    SkipDep,
    TaggedPostsDep,
    all_posts,
    count_total_posts,
)
from blog.services.users import UserDep

router = APIRouter(include_in_schema=False)


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


# --- Routes ---------------------------------------------------------


@router.get("/", name="home")
@router.get("/posts", name="posts")
async def home(
    request: Request,
    db: DbSession,
):
    total = await count_total_posts(db)
    posts = await all_posts(
        db, skip=0, limit=settings.posts_per_page
    )  # TODO no need in offset since that is always first page with first batch
    has_more = len(posts) < total

    return templates.TemplateResponse(
        request,
        "home.html",
        {
            **arrange(posts),
            "title": "Home",
            "limit": settings.posts_per_page,
            "has_more": has_more,
        },
    )


# Must be declared before /posts/{post_id} because FastAPI parses routes in the order of registration,
# and "new" would otherwise match post_id: int
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
    form: Annotated[PostFormInput, Form()],
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
        form (PostFormInput): the submitted fields, unvalidated.

    Returns:
        Response: a 303 redirect to the new post, or the form again with
        errors and the typed text if validation failed.

    """
    try:
        data = form.validated()
    except ValidationError as exception:
        return render_post_form(
            request, PostFormView(values=form, errors=form_errors(exception))
        )

    post = await posts.create(db, data, current_user)
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
    return render_post_form(
        request, PostFormView(values=post_to_input(post), post=post)
    )


@router.post("/posts/{post_id}/edit", name="update_post")
async def update_post(
    request: Request,
    post: PostDep,
    db: DbSession,
    form: Annotated[PostFormInput, Form()],
) -> Response:
    """
    Save an edit to a post.

    Args:
        request (Request): needed by the template and by url_for.
        post (PostDep): the post being edited.
        db (DbSession): current database session.
        form (PostFormInput): the submitted fields, unvalidated.

    Returns:
        Response: a 303 redirect to the post, or the form again with
        errors and the typed text if validation failed. The post is
        left untouched on failure, because the replacement happens after
        validation.

    """
    try:
        data = form.validated()
    except ValidationError as exception:
        return render_post_form(
            request,
            PostFormView(values=form, post=post, errors=form_errors(exception)),
        )

    await posts.replace(db, post, data)
    return RedirectResponse(
        request.url_for("post_page", post_id=post.id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


# One separate action, not a form field
@router.post("/posts/{post_id}/pin", name="toggle_pin")
async def toggle_pin(request: Request, post: PostDep, db: DbSession):
    await posts.set_pinned(db, post, pinned=not post.is_pinned)
    return RedirectResponse(
        request.url_for("edit_post", post_id=post.id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/posts/{post_id}", name="post_page")
async def post_page(request: Request, post: PostDep, db: DbSession):
    related, related_label = await posts.find_related(db, post)
    return templates.TemplateResponse(
        request,
        "post.html",
        {
            "post": post,
            "related": related,
            "related_label": related_label,
            "title": post.title,
        },
    )


@router.get("/tags", name="tags_index")
async def tags_index(
    request: Request,
    db: DbSession,
    skip: SkipDep = 0,
    limit: LimitDep = settings.posts_per_page,
):
    return templates.TemplateResponse(
        request,
        "tags.html",
        {"topics": await tags.all_topics(db, skip, limit), "title": "Topics"},
    )


@router.get("/tags/{tag}", name="get_tag")
def get_tag(request: Request, tag: str, tagged: TaggedPostsDep):
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            **arrange(tagged),
            "filter_tag": tag,
            "title": f"#{tag}",
        },
    )


@router.get("/users/{user_id}/posts", name="user_posts")
async def user_posts_page(
    request: Request,
    user: UserDep,
    db: DbSession,
    skip: SkipDep = 0,
    limit: LimitDep = settings.posts_per_page,
):
    return templates.TemplateResponse(
        request,
        "user_posts.html",
        {
            "posts": await posts.by_author(db, user.id, skip, limit),
            "user": user,
            "title": f"{user.username}'s posts",
        },
    )


@router.get("/about", name="about")
def about(request: Request):
    return templates.TemplateResponse(request, "about.html", {"title": "About"})


@router.get("/profile", name="profile")
def profile(request: Request):
    return templates.TemplateResponse(request, "profile.html", {"title": "Profile"})


@router.get("/login", name="login")
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"title": "Login"})


@router.get("/register", name="register")
def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html", {"title": "Register"})


@router.post("/posts/{post_id}/delete", name="delete_post")
async def delete_post(post: PostDep, db: DbSession):
    await posts.delete(db, post)
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
