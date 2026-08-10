"""The application object: what exists, where it is mounted, what it serves.

Nothing is decided here beyond assembly. Startup opens the connection
pool and shutdown releases it — the schema itself comes from Alembic, not
from anything run here — and the rest of the file is a list of what is
mounted where, which is the whole point of keeping it short.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from blog.core.config import STATIC_DIR, settings
from blog.core.logging import configure_logging
from blog.core.rate_limit import limiter
from blog.infrastructure import models  # noqa: F401
from blog.infrastructure.database import check_database_alive, setup_engine, teardown_engine
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
    """Open the pool on startup, and release it on shutdown."""
    setup_engine()
    yield

    await teardown_engine()


app = FastAPI(lifespan=lifespan)
app.state.limiter = limiter
# pyrefly: ignore [bad-argument-type]  # slowapi's handler is typed for its
# own exception, narrower than the Exception Starlette's signature wants.
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(RequestContextMiddleware)


app.mount("/static", RevalidatedStaticFiles(directory=STATIC_DIR), name="static")

# APIs logic
app.include_router(users.router, prefix=f"{API_PREFIX}/users", tags=["users"])
app.include_router(posts.router, prefix=f"{API_PREFIX}/posts", tags=["posts"])
app.include_router(tags.router, prefix=f"{API_PREFIX}/tags", tags=["tags"])


@app.get(f"{API_PREFIX}/health", include_in_schema=False)
async def health_check() -> dict[str, str]:
    """Report whether the app can reach its database.

    Not in the OpenAPI document: this answers a load balancer, not a
    client of the API, and does not belong next to the resources it lists.

    Checked on a connection of its own, outside the pool DbSession draws
    from — through that pool, an exhausted one would make this hang
    waiting for a connection instead of answering, which is exactly the
    moment a load balancer needs a fast refusal.

    Returns:
        dict[str, str]: `{"status": "ok"}` once the query succeeds.

    Raises:
        HTTPException: 503 when the database does not answer.
    """
    if not await check_database_alive():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database connection failed"
        )
    return {"status": "ok"}


# Frontend logic
app.include_router(pages.router)

register_error_handlers(app)
