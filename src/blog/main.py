"""The application object: what exists, where it is mounted, what it serves.

Nothing is decided here beyond assembly. Shutdown releases the pool — the
schema itself comes from Alembic, not from anything run here — and the
rest of the file is a list of what is mounted where, which is the whole
point of keeping it short.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from sqlalchemy import text

from blog.core.config import STATIC_DIR, settings
from blog.core.logging import configure_logging
from blog.infrastructure import models  # noqa: F401
from blog.infrastructure.database import DbSession, engine
from blog.presentation.api import API_PREFIX, posts, tags, users
from blog.presentation.errors import register_error_handlers
from blog.presentation.middleware import RequestContextMiddleware
from blog.presentation.static import RevalidatedStaticFiles
from blog.presentation.web import pages

configure_logging(settings)

# `models` is imported for its side effect — see that module's docstring
# for why (mapper registration), rather than for anything used here directly.


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """Release the pool on shutdown; nothing runs on startup."""
    yield

    await engine.dispose()


app = FastAPI(lifespan=lifespan)
app.add_middleware(RequestContextMiddleware)


app.mount("/static", RevalidatedStaticFiles(directory=STATIC_DIR), name="static")

# APIs logic
app.include_router(users.router, prefix=f"{API_PREFIX}/users", tags=["users"])
app.include_router(posts.router, prefix=f"{API_PREFIX}/posts", tags=["posts"])
app.include_router(tags.router, prefix=f"{API_PREFIX}/tags", tags=["tags"])


@app.get(f"{API_PREFIX}/health")
async def health_check(db: DbSession) -> dict[str, str]:
    """Report whether the app can reach its database.

    Args:
        db (DbSession): request-scoped session.

    Returns:
        dict[str, str]: `{"status": "ok"}` once the query succeeds.

    Raises:
        HTTPException: 503 when the database does not answer.
    """
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database connection failed"
        ) from exc
    return {"status": "ok"}


# Frontend logic
app.include_router(pages.router)

register_error_handlers(app)
