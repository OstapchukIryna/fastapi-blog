"""The application object: what exists, where it is mounted, what it serves.

Nothing is decided here beyond assembly. Startup creates the tables,
shutdown releases the pool, and the rest of the file is a list of what is
mounted where — which is the whole point of keeping it short.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from blog.core.config import MEDIA_DIR, STATIC_DIR
from blog.infrastructure import models  # noqa: F401
from blog.infrastructure.database import Base, engine
from blog.presentation.api import API_PREFIX, posts, tags, users
from blog.presentation.errors import register_error_handlers
from blog.presentation.static import RevalidatedStaticFiles
from blog.presentation.web import pages

# * `models` is imported for its side effect. create_all builds exactly
# * the tables whose classes are registered by the time it runs; the
# * routers would drag them in anyway, but then the set of tables would
# * depend on what somebody happened to import.


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """Create the schema on the way up, release the pool on the way down.

    create_all is a stand-in for migrations: it adds tables that do not
    exist and never alters one that does, so a column added to a model
    will not appear in an existing database.

    Args:
        _app (FastAPI): the application starting up. Unused — the hook
            is about process lifetime, not about this object.

    Yields:
        None: control, for as long as the application is serving.

    # TODO: replace with Alembic once migrations are on the roadmap.
    """
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    yield

    await engine.dispose()


app = FastAPI(lifespan=lifespan)

# Two mounts, two meanings. /static is shipped with the repository;
# /media is what people upload, and is not in version control.
#
# * Only /static revalidates. An uploaded picture is named after a fresh
# * uuid every time it changes, so its address already busts its own
# * cache — the file at a given /media path never has different contents.
app.mount("/static", RevalidatedStaticFiles(directory=STATIC_DIR), name="static")
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")

app.include_router(users.router, prefix=f"{API_PREFIX}/users", tags=["users"])
app.include_router(posts.router, prefix=f"{API_PREFIX}/posts", tags=["posts"])
app.include_router(tags.router, prefix=f"{API_PREFIX}/tags", tags=["tags"])

# * No prefix and out of the schema: these are addresses a person types,
# * not an API surface. Keeping them out of /openapi.json is also what
# * lets the contract test compare like with like.
app.include_router(pages.router)

register_error_handlers(app)
