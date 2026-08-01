from contextlib import asynccontextmanager

from fastapi import (
    FastAPI,
)
from fastapi.staticfiles import StaticFiles

from database import Base, engine
from error_handlers import register_error_handlers
from routers import pages, posts, tags, users


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

# Без префикса и вне схемы: это адреса, которые человек набирает,
# а не поверхность API.
app.include_router(pages.router)

register_error_handlers(app)
