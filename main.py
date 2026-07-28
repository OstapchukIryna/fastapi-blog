from collections.abc import Sequence
from typing import Annotated

import bcrypt
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

import models
from database import Base, engine, get_db
from error_handlers import register_error_handlers
from models import get_or_create_tags
from schemas import (
    PostCreate,
    PostDetail,
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
    """Подбирает записи по пересечению тегов.

    Заголовок секции возвращается вместе со списком: если общих тегов
    нет, блок не называется Related.
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
            # Сортировка по кортежу: сначала число общих тегов,
            # при равенстве — свежесть
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
    """Теги с числом записей, от популярных к редким.

    Один запрос с группировкой вместо загрузки всех тегов и подсчёта
    их записей в Python — считать умеет база.
    """
    rows = db.execute(
        select(models.Tag.name, func.count(models.Post.id))
        .join(models.Tag.posts)
        .group_by(models.Tag.id)
        .order_by(func.count(models.Post.id).desc(), models.Tag.name)
    ).all()
    return [(name, count) for name, count in rows]


def arrange(items: Sequence[models.Post]) -> dict:
    """Раскладывает список на ведущую запись и остальные.

    Без закреплённой ведущей становится первая по порядку, то есть
    самая свежая — выборки уже отсортированы по дате.
    """
    pinned = next((p for p in items if p.is_pinned), None)
    rest = [p for p in items if p is not pinned]
    lead = pinned or (rest.pop(0) if rest else None)
    return {"pinned": pinned, "lead": lead, "rest": rest}


# --- Страницы ---------------------------------------------------------


@app.get("/", include_in_schema=False, name="home")
@app.get("/posts", include_in_schema=False, name="posts")
def home(request: Request, db: DbSession):
    posts = db.execute(posts_query()).scalars().unique().all()
    return templates.TemplateResponse(
        request,
        "home.html",
        {**arrange(posts), "title": "Home"},
    )


@app.get("/posts/{post_id}", include_in_schema=False, name="post_page")
def post_page(request: Request, post_id: int, db: DbSession):
    post = db.execute(posts_query().where(models.Post.id == post_id)).scalars().first()
    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )

    related, related_label = find_related(db, post)
    return templates.TemplateResponse(
        request,
        "post.html",
        {
            "post": post,
            "related": related,
            "related_label": related_label,
            "title": post.title,
            "is_author": True,  # TODO: заменить реальной проверкой при авторизации
        },
    )


@app.get("/tags", include_in_schema=False, name="tags_index")
def tags_index(request: Request, db: DbSession):
    return templates.TemplateResponse(
        request, "tags.html", {"topics": all_topics(db), "title": "Topics"}
    )


@app.get("/tags/{tag}", include_in_schema=False, name="get_tag")
def get_tag(request: Request, tag: str, db: DbSession):
    tagged = (
        db.execute(posts_query().join(models.Post.tags).where(models.Tag.name == tag))
        .scalars()
        .unique()
        .all()
    )
    if not tagged:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found"
        )

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
def user_posts_page(request: Request, user_id: int, db: DbSession):
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    posts = (
        db.execute(posts_query().where(models.Post.user_id == user_id))
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
def delete_post(post_id: int, db: DbSession):
    post = db.get(models.Post, post_id)
    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )

    db.delete(post)
    db.commit()
    # 303, а не 302: только он гарантирует переход методом GET —
    # иначе обновление страницы повторит удаление
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)


# --- API --------------------------------------------------------------


@app.get("/api/posts", response_model=list[PostResponse])
def list_posts(db: DbSession):
    return db.execute(posts_query()).scalars().unique().all()


@app.get("/api/posts/{post_id}", response_model=PostDetail)
def get_post(post_id: int, db: DbSession):
    post = db.execute(posts_query().where(models.Post.id == post_id)).scalars().first()
    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )
    return post


@app.post("/api/posts", response_model=PostDetail, status_code=status.HTTP_201_CREATED)
def create_post(post: PostCreate, db: DbSession):
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
def get_tag_posts(tag: str, db: DbSession):
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
        # Одно сообщение на оба случая: раздельные ответы позволяют
        # перебором выяснить, какие адреса зарегистрированы
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
        # Подстраховка от гонки: два запроса могли одновременно пройти
        # проверку на clash выше и столкнуться уже на уровне БД
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered",
        ) from None
    db.refresh(new_user)
    return new_user


@app.get("/api/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: DbSession):
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return user


@app.get("/api/users/{user_id}/posts", response_model=list[PostResponse])
def get_user_posts(user_id: int, db: DbSession):
    if db.get(models.User, user_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    return (
        db.execute(posts_query().where(models.Post.user_id == user_id))
        .scalars()
        .unique()
        .all()
    )
