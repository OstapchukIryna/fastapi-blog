from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import (
    Depends,
    FastAPI,
    Form,
    Request,
    Response,
    status,
)
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

import models
from database import Base, engine, get_db
from error_handlers import register_error_handlers
from models import get_or_create_tags
from routers import posts, tags, users
from routers.posts import (
    PostDep,
    PostFormView,
    arrange,
    find_related,
    post_to_input,
    posts_query,
    set_pinned,
)
from routers.tags import TaggedPostsDep, all_topics
from routers.users import UserDep, current_author
from schemas import PostFormInput
from templating import templates


# async await of creating db tables if they're not exist
@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/media", StaticFiles(directory="media"), name="media")


app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(posts.router, prefix="/api/posts", tags=["posts"])
app.include_router(tags.router, prefix="/api/tags", tags=["tags"])

register_error_handlers(app)

DbSession = Annotated[AsyncSession, Depends(get_db)]


# --- Helpers ---------------------------------------------------------


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


@app.get("/", include_in_schema=False, name="home")
@app.get("/posts", include_in_schema=False, name="posts")
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
@app.get("/posts/new", include_in_schema=False, name="new_post")
def new_post_form(request: Request) -> Response:
    """
    Show an empty form for a new post.

    Args:
        request (Request): needed by the template.

    Returns:
        Response: the blank form page.

    """
    return render_post_form(request, PostFormView(values=PostFormInput()))


@app.post("/posts/new", include_in_schema=False, name="create_post_page")
async def create_post_page(
    request: Request, db: DbSession, form: Annotated[PostFormInput, Form()]
) -> Response:
    """
    Create a post from the submitted form.

    FastAPI fills PostFormInput itself: a model behind Form() describes a
    form the way a model in the body describes JSON.

    Args:
        request (Request): needed by the template and by url_for.
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
        author=await current_author(db),
        tags=await get_or_create_tags(db, data.tags),
    )
    db.add(post)
    await db.commit()
    await db.refresh(post, attribute_names=["author"])
    return RedirectResponse(
        request.url_for("post_page", post_id=post.id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.get("/posts/{post_id}/edit", include_in_schema=False, name="edit_post")
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


@app.post("/posts/{post_id}/edit", include_in_schema=False, name="update_post")
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
@app.post("/posts/{post_id}/pin", include_in_schema=False, name="toggle_pin")
async def toggle_pin(request: Request, post: PostDep, db: DbSession):
    await set_pinned(db, post, pinned=not post.is_pinned)
    await db.commit()
    return RedirectResponse(
        request.url_for("edit_post", post_id=post.id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.get("/posts/{post_id}", include_in_schema=False, name="post_page")
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


@app.get("/tags", include_in_schema=False, name="tags_index")
async def tags_index(request: Request, db: DbSession):
    return templates.TemplateResponse(
        request, "tags.html", {"topics": await all_topics(db), "title": "Topics"}
    )


@app.get("/tags/{tag}", include_in_schema=False, name="get_tag")
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


@app.get("/users/{user_id}/posts", include_in_schema=False, name="user_posts")
async def user_posts_page(request: Request, user: UserDep, db: DbSession):
    result = await db.execute(posts_query().where(models.Post.user_id == user.id))
    posts = result.scalars().unique().all()
    return templates.TemplateResponse(
        request,
        "user_posts.html",
        {"posts": posts, "user": user, "title": f"{user.username}'s posts"},
    )


@app.get("/about", include_in_schema=False, name="about")
def about(request: Request):
    return templates.TemplateResponse(request, "about.html", {"title": "About"})


@app.get("/profile", include_in_schema=False, name="profile")
def profile(request: Request):
    return templates.TemplateResponse(request, "profile.html", {"title": "Profile"})


@app.get("/login", include_in_schema=False, name="login")
def login(request: Request):
    return templates.TemplateResponse(request, "login.html", {"title": "Login"})


@app.post("/posts/{post_id}/delete", include_in_schema=False, name="delete_post")
async def delete_post(post: PostDep, db: DbSession):
    await db.delete(post)
    await db.commit()
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
