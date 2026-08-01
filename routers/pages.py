"""
The HTML side of the site: every page a person opens in a browser.

Separate from routers/posts.py and its neighbours because those answer
JSON and these answer pages, and the two had grown different needs — the
form state below, the error wording, the arrangement of a front page —
none of which the API has any use for. They lived in the API router and
in main.py, which left main.py holding the application factory and
sixteen page handlers at once.

Route names are unchanged: url_for in the templates depends on them.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Annotated

from fastapi import APIRouter, Form, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

import models
from auth import CurrentUser
from database import DbSession
from models import get_or_create_tags
from routers.posts import PostDep, find_related, posts_query, set_pinned
from routers.tags import TaggedPostsDep, all_topics
from routers.users import UserDep
from schemas import PostFormInput
from templating import templates

router = APIRouter(include_in_schema=False)


# --- Страничное состояние ---------------------------------------
# Переехало из routers/posts.py: там это лежало рядом с JSON-API,
# который ими не пользуется ни разу — форма, её состояние и раскладка
# главной существуют только ради шаблонов.


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


def form_errors(exception: ValidationError) -> dict[str, str]:
    """
    Generate human-readable exeptions

    Args:
        exception (ValidationError): exeption from pydantic validation

    Returns:
        dict[str, str]: dictionary with field name and error message

    """
    errors: dict[str, str] = {}
    for error in exception.errors():
        field = str(error["loc"][0]) if error["loc"] else "form"
        context = error.get("ctx", {})
        kind = error["type"]

        if kind == "string_too_short" and context.get("min_length") == 1:
            message = "Required."
        elif kind == "string_too_short":
            message = f"At least {context['min_length']} characters."
        elif kind == "string_too_long":
            message = f"At most {context['max_length']} characters."
        else:
            message = error["msg"]

        errors.setdefault(field, message)
    return errors


def render_post_form(request: Request, view: PostFormView) -> Response:
    """
    Draw the post form in the given state.

    Serves both creating and editing: the fields are identical,
    and the differences — heading, submit target, button label — are
    derived from the view.

    Args:
        request (Request): needed by Jinja2Templates and url_for.
        view (PostFormView): typed values, the post being edited, and errors if exist.

    Returns:
        Response: the form page, with status 422 if the view holds errors.

    """
    return templates.TemplateResponse(
        request,
        "post_form.html",
        {"view": view, "title": view.title},
        status_code=view.status_code,
    )


# --- Routes ---------------------------------------------------------


@router.get("/", include_in_schema=False, name="home")
@router.get("/posts", include_in_schema=False, name="posts")
async def home(request: Request, db: DbSession):
    result = await db.execute(posts_query())
    posts = result.scalars().unique().all()
    return templates.TemplateResponse(
        request,
        "home.html",
        {**arrange(posts), "title": "Home"},
    )


# Must be declared before /posts/{post_id} because FastAPI parses routes in the order of registration,
# and "new" would otherwise match post_id: int and give 422
@router.get("/posts/new", include_in_schema=False, name="new_post")
def new_post_form(request: Request) -> Response:
    """
    Show an empty form for a new post.

    Args:
        request (Request): needed by the template.

    Returns:
        Response: the blank form page.

    """
    return render_post_form(request, PostFormView(values=PostFormInput()))


@router.post("/posts/new", include_in_schema=False, name="create_post_page")
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

    post = models.Post(
        title=data.title,
        summary=data.summary,
        content=data.content,
        # The relationship wants the User, not its id — assigning the id
        # here made SQLAlchemy try to treat an int as a User.
        author=current_user,
        tags=await get_or_create_tags(db, data.tags),
    )
    db.add(post)
    await db.commit()
    await db.refresh(post, attribute_names=["author"])
    return RedirectResponse(
        request.url_for("post_page", post_id=post.id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/posts/{post_id}/edit", include_in_schema=False, name="edit_post")
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


@router.post("/posts/{post_id}/edit", include_in_schema=False, name="update_post")
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
        left untouched on failure, because assignment happens after
        validation.

    """
    try:
        data = form.validated()
    except ValidationError as exception:
        return render_post_form(
            request,
            PostFormView(values=form, post=post, errors=form_errors(exception)),
        )

    post.title = data.title
    post.summary = data.summary
    post.content = data.content
    post.tags = await get_or_create_tags(db, data.tags)
    await db.commit()
    return RedirectResponse(
        request.url_for("post_page", post_id=post.id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


# One separate action, not a form field
@router.post("/posts/{post_id}/pin", include_in_schema=False, name="toggle_pin")
async def toggle_pin(request: Request, post: PostDep, db: DbSession):
    await set_pinned(db, post, pinned=not post.is_pinned)
    await db.commit()
    return RedirectResponse(
        request.url_for("edit_post", post_id=post.id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/posts/{post_id}", include_in_schema=False, name="post_page")
async def post_page(request: Request, post: PostDep, db: DbSession):
    related, related_label = await find_related(db, post)
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


@router.get("/tags", include_in_schema=False, name="tags_index")
async def tags_index(request: Request, db: DbSession):
    return templates.TemplateResponse(
        request, "tags.html", {"topics": await all_topics(db), "title": "Topics"}
    )


@router.get("/tags/{tag}", include_in_schema=False, name="get_tag")
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


@router.get("/users/{user_id}/posts", include_in_schema=False, name="user_posts")
async def user_posts_page(request: Request, user: UserDep, db: DbSession):
    result = await db.execute(posts_query().where(models.Post.user_id == user.id))
    posts = result.scalars().unique().all()
    return templates.TemplateResponse(
        request,
        "user_posts.html",
        {"posts": posts, "user": user, "title": f"{user.username}'s posts"},
    )


@router.get("/about", include_in_schema=False, name="about")
def about(request: Request):
    return templates.TemplateResponse(request, "about.html", {"title": "About"})


@router.get("/profile", include_in_schema=False, name="profile")
def profile(request: Request):
    return templates.TemplateResponse(request, "profile.html", {"title": "Profile"})


@router.get("/login", include_in_schema=False, name="login")
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"title": "Login"})


@router.get("/register", include_in_schema=False, name="register")
async def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html", {"title": "Register"})


@router.post("/posts/{post_id}/delete", include_in_schema=False, name="delete_post")
async def delete_post(post: PostDep, db: DbSession):
    await db.delete(post)
    await db.commit()
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
