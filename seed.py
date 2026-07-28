"""Наполнение базы демонстрационными записями.

Запуск:
    uv run python seed.py
    uv run python seed.py --reset    # снести таблицы и создать заново

Скрипт идемпотентен: повторный запуск ничего не дублирует.
"""

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import NotRequired, TypedDict

import bcrypt
from sqlalchemy import select
from sqlalchemy.orm import Session

import models
from database import Base, engine
from models import get_or_create_tags

CONTENT_DIR = Path(__file__).parent / "content"

AUTHOR = {
    "username": "called_mad",
    "email": "hello@example.com",
    "password": "change-me-please",  # TODO: не для боевого окружения
}


class PostSeed(TypedDict):
    slug: str
    title: str
    summary: str
    tags: list[str]
    date: datetime
    pinned: NotRequired[bool]


# Метаданные здесь, тексты в content/*.md — правится в редакторе
# как обычный markdown, а не внутри строкового литерала
POSTS: list[PostSeed] = [
    {
        "slug": "modern-python-tooling",
        "title": "I replaced pip, black and mypy in one afternoon",
        "summary": (
            "uv, ruff and pyrefly in place of four older tools — what the "
            "switch actually changed, and where the old ones still matter."
        ),
        "tags": ["tooling", "python"],
        "date": datetime(2026, 7, 26, 10, 0, tzinfo=UTC),
    },
    {
        "slug": "pydantic-validators",
        "title": "The Pydantic validator mistake that returns None",
        "summary": (
            "A validator that forgets to return does not fail loudly. It "
            "quietly sets the field to None."
        ),
        "tags": ["pydantic", "python"],
        "date": datetime(2026, 7, 22, 9, 30, tzinfo=UTC),
    },
    {
        "slug": "threads-vs-processes",
        "title": "Threads didn't make it faster. Processes did.",
        "summary": (
            "Twelve images, two halves of one script, and two opposite "
            "results from the same tool. The GIL explains both."
        ),
        "tags": ["async", "python"],
        "date": datetime(2026, 7, 18, 18, 15, tzinfo=UTC),
        "pinned": True,
    },
    {
        "slug": "window-functions-cte",
        "title": "Why you can't filter a window function in WHERE",
        "summary": (
            "The column exists four lines above the error. The problem is "
            "not where it is, but when it is evaluated."
        ),
        "tags": ["sql"],
        "date": datetime(2026, 7, 12, 14, 0, tzinfo=UTC),
    },
    {
        "slug": "dict-resize",
        "title": "What actually happens when a dict resizes",
        "summary": (
            "Two-thirds full, powers of two, and one unlucky insert that "
            "pays for rehashing the entire table."
        ),
        "tags": ["python", "internals"],
        "date": datetime(2026, 7, 5, 11, 45, tzinfo=UTC),
    },
]


def load_content(slug: str) -> str:
    path = CONTENT_DIR / f"{slug}.md"
    if not path.exists():
        raise FileNotFoundError(f"no file {path}")
    return path.read_text(encoding="utf-8")


def get_or_create_author(db: Session) -> models.User:
    user = (
        db.execute(
            select(models.User).where(models.User.username == AUTHOR["username"])
        )
        .scalars()
        .first()
    )

    if user is not None:
        return user

    user = models.User(
        username=AUTHOR["username"],
        email=AUTHOR["email"],
        password_hash=bcrypt.hashpw(
            AUTHOR["password"].encode(), bcrypt.gensalt()
        ).decode(),
    )
    db.add(user)
    db.flush()  # чтобы получить user.id до коммита
    return user


def seed() -> None:
    with Session(engine) as db:
        author = get_or_create_author(db)

        created = 0
        for item in POSTS:
            # Идемпотентность по заголовку: колонки slug в модели нет,
            # а заголовки здесь уникальны
            exists = (
                db.execute(
                    select(models.Post).where(models.Post.title == item["title"])
                )
                .scalars()
                .first()
            )
            if exists is not None:
                continue

            db.add(
                models.Post(
                    title=item["title"],
                    summary=item["summary"],
                    content=load_content(item["slug"]),
                    date_posted=item["date"],
                    is_pinned=item.get("pinned", False),
                    author=author,
                    tags=get_or_create_tags(db, item["tags"]),
                )
            )
            created += 1

        db.commit()
        print(f"author: {author.username}, added posts: {created}")


if __name__ == "__main__":
    if "--reset" in sys.argv:
        Base.metadata.drop_all(bind=engine)
        print("tables dropped")

    Base.metadata.create_all(bind=engine)
    seed()
