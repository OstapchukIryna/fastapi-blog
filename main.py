from collections.abc import Sequence
from typing import Annotated

import bcrypt
from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

import models
from database import Base, engine, get_db
from error_handlers import register_error_handlers
from models import get_or_create_tags
from schemas import (
    PostCreate,
    PostDetail,
    PostForm,
    PostResponse,
    TagCount,
    UserCreate,
    UserResponse,
)
from templating import templates

# TODO: заменить на Alembic — create_all не умеет менять существующие таблицы
Base.metadata.create_all(bind=engine)

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/media", StaticFiles(directory="media"), name="media")

register_error_handlers(app)

DbSession = Annotated[Session, Depends(get_db)]


# --- Вспомогательное -------------------------------------------------


def posts_query():
    """Базовая выборка записей с подтянутыми связями.

    selectinload и joinedload здесь не оптимизация «на будущее»: без них
    обращение к post.tags в шаблоне порождает отдельный запрос на каждую
    запись — та самая проблема N+1.
    """
    return (
        select(models.Post)
        .options(
            selectinload(models.Post.tags),
            joinedload(models.Post.author),
        )
        .order_by(models.Post.date_posted.desc())
    )


def find_related(
    db: Session, current: models.Post, limit: int = 2
) -> tuple[list[dict], str]:
    """
    Find related posts by tags. Returns a list of related posts with shared tags.

    Args:
        db (Session): current database session
        current (models.Post): current post
        limit (int, optional): Limit of related posts to return. Defaults to 2.

    Returns:
        tuple[list[dict], str]: List of related posts with shared tags
        and a label indicating the type of relation

    """
    current_tags = {tag.name for tag in current.tags}

    if current_tags:
        candidates = (
            db.execute(
                posts_query()
                .join(models.Post.tags)
                .where(
                    models.Tag.name.in_(current_tags),
                    models.Post.id != current.id,
                )
            )
            .scalars()
            .unique()
            .all()
        )

        matched = [
            {"post": p, "shared": sorted(current_tags & {t.name for t in p.tags})}
            for p in candidates
        ]
        if matched:
            matched.sort(
                key=lambda m: (len(m["shared"]), m["post"].date_posted), reverse=True
            )
            return matched[:limit], "Related"

    fallback = (
        db.execute(posts_query().where(models.Post.id != current.id).limit(limit))
        .scalars()
        .unique()
        .all()
    )
    return [{"post": p, "shared": []} for p in fallback], "More posts"


def all_topics(db: Session) -> list[tuple[str, int]]:
    """
    Sort tags by counting posts with them. Return list of tuples with tag name and count of posts.

    Args:
        db (Session): current database session

    Returns:
        list[tuple[str, int]]: List of tuples containing tag names and their respective post counts

    """
    rows = db.execute(
        select(models.Tag.name, func.count(models.Post.id))
        .join(models.Tag.posts)
        .group_by(models.Tag.id)
        .order_by(func.count(models.Post.id).desc(), models.Tag.name)
    ).all()
    return [(name, count) for name, count in rows]


def current_author(db: Session) -> models.User:
    """
    Get author of current post.

    Args:
        db (Session): current database session

    Raises:
        HTTPException: If no author is found in the database, raises a 500 Internal Server Error with a message to run the seed script.

    Returns:
        models.User: The first user found in the database, representing the author of the current post.
    """
    author = db.execute(select(models.User).order_by(models.User.id)).scalars().first()
    if author is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No author in the database. Run: uv run python seed.py",
        )
    return author


def split_tags(raw: str) -> list[str]:
    """
    Split tags from a string and return them in a list.

    Args:
        raw (str): String of tags separated by comma

    Returns:
        list[str]: list of tags

    """
    return [part for part in (chunk.strip() for chunk in raw.split(",")) if part]


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


def set_pinned(db: Session, post: models.Post, *, pinned: bool) -> None:
    """
    Set pinned status for a post

    Args:
        db (Session): current database session
        post (models.Post): post to be pinned
        pinned (bool): if True, pin the post; if False, unpin the post

    """
    if pinned:
        db.execute(
            update(models.Post)
            .where(models.Post.id != post.id, models.Post.is_pinned.is_(True))
            .values(is_pinned=False)
        )
    post.is_pinned = pinned


def arrange(items: Sequence[models.Post]) -> dict:
    """
    Separate posts onto one pinned and others. Rearrange them

    Args:
        items (Sequence[models.Post]): sequence of posts

    Returns:
        dict: Dictionary containing pinned post, lead post, and the rest of the posts

    """
    pinned = next((p for p in items if p.is_pinned), None)
    rest = [p for p in items if p is not pinned]
    lead = pinned or (rest.pop(0) if rest else None)
    return {"pinned": pinned, "lead": lead, "rest": rest}


# --- Dependencies ------------------------------------------------------
# Create dependencies for loading posts, users, and tagged posts from the database.
# These dependencies will be used in the route handlers to fetch the required data based on the provided parameters.
# Prevent code duplication and ensure consistent error handling for missing resources.


def load_post(post_id: int, db: DbSession) -> models.Post:
    """Returns post by id, otherwise 404."""
    post = db.execute(posts_query().where(models.Post.id == post_id)).scalars().first()
    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )
    return post


def load_user(user_id: int, db: DbSession) -> models.User:
    """Returns user by id, otherwise 404."""
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return user


def load_tagged_posts(tag: str, db: DbSession) -> Sequence[models.Post]:
    """Returns posts by tag, otherwise 404. If tags are not found or no posts with this tag, return 404."""
    posts = (
        db.execute(posts_query().join(models.Post.tags).where(models.Tag.name == tag))
        .scalars()
        .unique()
        .all()
    )
    if not posts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found"
        )
    return posts


PostDep = Annotated[models.Post, Depends(load_post)]
UserDep = Annotated[models.User, Depends(load_user)]
TaggedPostsDep = Annotated[Sequence[models.Post], Depends(load_tagged_posts)]


# --- Routes ---------------------------------------------------------


@app.get("/", include_in_schema=False, name="home")
@app.get("/posts", include_in_schema=False, name="posts")
def home(request: Request, db: DbSession):
    posts = db.execute(posts_query()).scalars().unique().all()
    return templates.TemplateResponse(
        request,
        "home.html",
        {**arrange(posts), "title": "Home"},
    )


def render_post_form(
    request: Request,
    *,
    mode: str,
    values: dict[str, str],
    errors: dict[str, str] | None = None,
    post: models.Post | None = None,
    status_code: int = status.HTTP_200_OK,
):
    return templates.TemplateResponse(
        request,
        "post_form.html",
        {
            "mode": mode,
            "values": values,
            "errors": errors or {},
            "post": post,
            "title": "New post" if mode == "new" else "Edit post",
        },
        status_code=status_code,
    )


# Must be declared before /posts/{post_id} because FastAPI parses routes in the order of registration,
# and "new" would otherwise match post_id: int and give 422
@app.get("/posts/new", include_in_schema=False, name="new_post")
def new_post_form(request: Request):
    return render_post_form(
        request,
        mode="new",
        values={"title": "", "summary": "", "content": "", "tags": ""},
    )


@app.post("/posts/new", include_in_schema=False, name="create_post_page")
def create_post_page(
    request: Request,
    db: DbSession,
    title: Annotated[str, Form()] = "",
    summary: Annotated[str, Form()] = "",
    content: Annotated[str, Form()] = "",
    tags: Annotated[str, Form()] = "",
):
    values = {"title": title, "summary": summary, "content": content, "tags": tags}
    try:
        data = PostForm(
            title=title, summary=summary, content=content, tags=split_tags(tags)
        )
    except ValidationError as exception:
        return render_post_form(
            request,
            mode="new",
            values=values,
            errors=form_errors(exception),
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    post = models.Post(
        title=data.title,
        summary=data.summary,
        content=data.content,
        author=current_author(db),
        tags=get_or_create_tags(db, data.tags),
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return RedirectResponse(
        request.url_for("post_page", post_id=post.id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.get("/posts/{post_id}/edit", include_in_schema=False, name="edit_post")
def edit_post_form(request: Request, post: PostDep):
    return render_post_form(
        request,
        mode="edit",
        post=post,
        values={
            "title": post.title,
            "summary": post.summary,
            "content": post.content,
            "tags": ", ".join(tag.name for tag in post.tags),
        },
    )


@app.post("/posts/{post_id}/edit", include_in_schema=False, name="update_post")
def update_post(
    request: Request,
    post: PostDep,
    db: DbSession,
    title: Annotated[str, Form()] = "",
    summary: Annotated[str, Form()] = "",
    content: Annotated[str, Form()] = "",
    tags: Annotated[str, Form()] = "",
):
    values = {"title": title, "summary": summary, "content": content, "tags": tags}
    try:
        data = PostForm(
            title=title, summary=summary, content=content, tags=split_tags(tags)
        )
    except ValidationError as exception:
        return render_post_form(
            request,
            mode="edit",
            post=post,
            values=values,
            errors=form_errors(exception),
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    post.title = data.title
    post.summary = data.summary
    post.content = data.content
    post.tags = get_or_create_tags(db, data.tags)
    db.commit()
    return RedirectResponse(
        request.url_for("post_page", post_id=post.id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


# One separate action, not a form field
@app.post("/posts/{post_id}/pin", include_in_schema=False, name="toggle_pin")
def toggle_pin(request: Request, post: PostDep, db: DbSession):
    set_pinned(db, post, not post.is_pinned)
    db.commit()
    return RedirectResponse(
        request.url_for("edit_post", post_id=post.id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.get("/posts/{post_id}", include_in_schema=False, name="post_page")
def post_page(request: Request, post: PostDep, db: DbSession):
    related, related_label = find_related(db, post)
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
def tags_index(request: Request, db: DbSession):
    return templates.TemplateResponse(
        request, "tags.html", {"topics": all_topics(db), "title": "Topics"}
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
def user_posts_page(request: Request, user: UserDep, db: DbSession):
    posts = (
        db.execute(posts_query().where(models.Post.user_id == user.id))
        .scalars()
        .unique()
        .all()
    )
    return templates.TemplateResponse(
        request,
        "user_posts.html",
        {"posts": posts, "user": user, "title": f"{user.username}'s posts"},
    )


@app.get("/about", include_in_schema=False, name="about")
def about(request: Request):
    return templates.TemplateResponse(request, "about.html", {"title": "About"})


@app.get("/login", include_in_schema=False, name="login")
def login(request: Request):
    return templates.TemplateResponse(request, "login.html", {"title": "Login"})


@app.post("/posts/{post_id}/delete", include_in_schema=False, name="delete_post")
def delete_post(post: PostDep, db: DbSession):
    db.delete(post)
    db.commit()
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)


# --- API --------------------------------------------------------------


@app.get("/api/posts", response_model=list[PostResponse])
def list_posts(db: DbSession):
    return db.execute(posts_query()).scalars().unique().all()


@app.get("/api/posts/{post_id}", response_model=PostDetail)
def get_post(post: PostDep):
    return post


@app.post("/api/posts", response_model=PostDetail, status_code=status.HTTP_201_CREATED)
def create_post(post: PostCreate, db: DbSession):
    # The only 404 check left in the route: the author comes in the request body,
    # not in the path, and the dependency on the path parameter will not see it.
    if db.get(models.User, post.user_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    new_post = models.Post(
        title=post.title,
        summary=post.summary,
        content=post.content,
        user_id=post.user_id,
        tags=get_or_create_tags(db, post.tags),
    )
    db.add(new_post)
    db.commit()
    db.refresh(new_post)
    return new_post


@app.get("/api/tags", response_model=list[TagCount])
def list_tags(db: DbSession):
    return [{"name": name, "count": count} for name, count in all_topics(db)]


@app.get("/api/tags/{tag}/posts", response_model=list[PostResponse])
def get_tag_posts(posts: TaggedPostsDep):
    return posts


@app.post(
    "/api/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
def create_user(user: UserCreate, db: DbSession):
    clash = (
        db.execute(
            select(models.User).where(
                (models.User.username == user.username)
                | (models.User.email == user.email)
            )
        )
        .scalars()
        .first()
    )

    if clash is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered",
        )

    new_user = models.User(
        username=user.username,
        email=user.email,
        password_hash=bcrypt.hashpw(user.password.encode(), bcrypt.gensalt()).decode(),
    )
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError:
        # Race prevention
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered",
        ) from None
    db.refresh(new_user)
    return new_user


@app.get("/api/users/{user_id}", response_model=UserResponse)
def get_user(user: UserDep):
    return user


@app.get("/api/users/{user_id}/posts", response_model=list[PostResponse])
def get_user_posts(user: UserDep, db: DbSession):
    return (
        db.execute(posts_query().where(models.Post.user_id == user.id))
        .scalars()
        .unique()
        .all()
    )
