from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from blog.core.config import MEDIA_DIR, STATIC_DIR
from blog.infrastructure import models  # noqa: F401
from blog.infrastructure.database import Base, engine
from blog.presentation.api import posts, tags, users
from blog.presentation.errors import register_error_handlers
from blog.presentation.web import pages


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

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")


app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(posts.router, prefix="/api/posts", tags=["posts"])
app.include_router(tags.router, prefix="/api/tags", tags=["tags"])

app.include_router(pages.router)

register_error_handlers(app)
