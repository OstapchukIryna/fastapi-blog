"""Seed the database with the real posts this blog started from.

    uv run python seed.py
    uv run python seed.py --reset    # drop the tables and rebuild them

Idempotent: running it twice adds nothing the second time, which is what
lets the test harness call it before every run without thinking about it.

Five real posts is enough for the tests and not enough to see pagination.
Volume is populate.py's job, and that script is destructive.
"""

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import NotRequired, TypedDict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from blog.core.security import hash_password
from blog.infrastructure import models
from blog.infrastructure.database import AsyncSessionLocal, Base, engine
from blog.services import tags as tag_service

CONTENT_DIR = Path(__file__).parent / "content"

AUTHOR = {
    "username": "called_mad",
    "email": "blue.hunde@gmail.com",
    # TODO: fine for a local database, not for anything reachable.
    "password": "TestPassword123",
}


class PostSeed(TypedDict):
    """One article's metadata; its prose is read from content/<slug>.md.

    Attributes:
        slug (str): the Markdown file's name, without the extension.
        title (str): headline, and the key idempotency is judged on.
        summary (str): the listing blurb.
        tags (list[str]): labels, created on demand.
        date (datetime): publication time, timezone-aware.
        pinned (NotRequired[bool]): whether this leads the front page.
    """

    slug: str
    title: str
    summary: str
    tags: list[str]
    date: datetime
    pinned: NotRequired[bool]


# * Metadata here, prose in content/*.md. An article is edited in an
# * editor as ordinary Markdown rather than inside a string literal,
# * where every quote and backslash would have to be escaped.
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
    """Read an article's body from content/.

    Args:
        slug (str): the file's name without its extension.

    Returns:
        str: the Markdown source.

    Raises:
        FileNotFoundError: the metadata names a file that is not there.
            Loud on purpose — a post seeded with an empty body would be
            harder to notice than a script that stops.
    """
    path = CONTENT_DIR / f"{slug}.md"
    if not path.exists():
        raise FileNotFoundError(f"no file {path}")
    return path.read_text(encoding="utf-8")


async def get_or_create_author(db: AsyncSession) -> models.User:
    """Return the blog's author, creating the account on a first run.

    Args:
        db (AsyncSession): session to query and stage through.

    Returns:
        models.User: the author, whether just made or already there.
    """
    result = await db.execute(
        select(models.User).where(models.User.username == AUTHOR["username"])
    )
    user = result.scalars().first()

    if user is not None:
        return user

    user = models.User(
        # ! Hashed by the same function registration uses. pwdlib is
        # ! built with Argon2 only: it does not recognise a bcrypt hash
        # ! and raises instead of answering "no match", so a seeded
        # ! author hashed any other way could not sign in at all — and
        # ! the failure surfaced as a 500 rather than a 401.
        username=AUTHOR["username"],
        email=AUTHOR["email"].lower(),
        password_hash=hash_password(AUTHOR["password"]),
    )
    db.add(user)
    await db.flush()  # assigns user.id without ending the transaction
    return user


async def seed() -> None:
    """Add any of the listed posts that are not in the database yet."""
    async with AsyncSessionLocal() as db:
        author = await get_or_create_author(db)

        created = 0
        for item in POSTS:
            # * Idempotency keyed on the title: the model has no slug
            # * column, and the titles in this file are unique.
            result = await db.execute(
                select(models.Post).where(models.Post.title == item["title"])
            )
            exists = result.scalars().first()
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
                    tags=await tag_service.get_or_create(db, item["tags"]),
                )
            )
            created += 1

        await db.commit()
        print(f"author: {author.username}, added posts: {created}")


async def main() -> None:
    """Create the tables, optionally dropping them first, then seed."""
    async with engine.begin() as conn:
        if "--reset" in sys.argv:
            await conn.run_sync(Base.metadata.drop_all)
            print("tables dropped")
        await conn.run_sync(Base.metadata.create_all)

    await seed()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
