"""The engine, the session factory, and the dependency that hands one out.

One engine per process and one session per request. The session is opened
by a FastAPI dependency and closed when the response is finished; nothing
here commits, because deciding when a change is final belongs to the
service performing it.
"""

import os
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# The default is a file in the working directory, which is what makes a
# fresh clone runnable without configuration. Test runs point this at a
# throwaway file so a write endpoint never touches the development data.
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./blog.db")

engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    # ! SQLite refuses a connection used from a thread other than the one
    # ! that opened it. The async driver moves work between threads by
    # ! design, so the check has to come off — it guards an assumption
    # ! that does not hold here.
    connect_args={"check_same_thread": False},
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    # * Objects stay usable after commit. With the default, every
    # * attribute read on a committed object triggers a reload — which in
    # * async code means IO from a template that has no session to do it
    # * with, and an error a long way from the commit that caused it.
    # * Services return ORM objects to the layer above; this is what
    # * makes that safe.
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Declarative base every model inherits from.

    Also the registry `create_all` reads: a table exists at startup only
    if its class has been imported by then, which is why `main` imports
    the models package explicitly rather than relying on the routers to
    drag it in.
    """


async def get_db() -> AsyncIterator[AsyncSession]:
    """Open a session for one request and close it afterwards.

    Yields:
        AsyncSession: a session bound to this request. Uncommitted work
            is discarded when the request ends, so a service that raises
            midway leaves nothing behind.
    """
    async with AsyncSessionLocal() as session:
        yield session


# ! This alias must exist at runtime. FastAPI reads annotations to
# ! resolve dependencies, so moving the import under TYPE_CHECKING does
# ! not fail loudly — `db` silently becomes a query parameter and the
# ! endpoint starts answering 422 with nothing in the log. This is why
# ! flake8-type-checking is disabled for the project.
DbSession = Annotated[AsyncSession, Depends(get_db)]
