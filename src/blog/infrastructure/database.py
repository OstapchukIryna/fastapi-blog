"""The engine, the session factory, and the dependency that hands one out.

One engine per process and one session per request. The session is opened
by a FastAPI dependency and closed when the response is finished; nothing
here commits, because deciding when a change is final belongs to the
service performing it.
"""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from blog.core.config import settings

# * Populated by setup_engine(), not here: tying creation to import rather
# * than to the application's own lifespan makes shutdown a polite fiction
# * — engine.dispose() runs, but nothing ever owned starting it. main.py's
# * lifespan calls setup_engine() before yield and teardown_engine() after,
# * so the pool's lifetime actually matches the app's.
engine: AsyncEngine | None = None
AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None


class Base(DeclarativeBase):
    """Declarative base every model inherits from."""


def setup_engine() -> None:
    """Create the engine and session factory. Called once, from lifespan.

    pool_pre_ping=True: without it, a connection the database closed for
    being idle too long is handed out anyway, and the first query on it
    fails with a broken-connection error that has nothing to do with the
    query itself — the "first request every morning is a 500" class of
    bug. The extra round trip this adds per checkout is the cheap side of
    that trade.
    """
    global engine, AsyncSessionLocal
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def teardown_engine() -> None:
    """Dispose the engine and drop the session factory. Called once, from lifespan."""
    global engine, AsyncSessionLocal
    if engine is not None:
        await engine.dispose()
    engine = None
    AsyncSessionLocal = None


async def get_db() -> AsyncIterator[AsyncSession]:
    """Open a session for one request and close it afterwards.

    The rollback below is not what keeps a failed request's writes out of
    the database — close() returning the connection to the pool already
    does that, because SQLAlchemy issues a ROLLBACK on a connection that
    goes back with an open transaction. It is here so that guarantee does
    not live only in the pool's behaviour: an explicit rollback on the
    session itself is what a reader can see without knowing that detail,
    and what stays true even if the connection-level behaviour ever
    changed underneath it.
    """
    assert AsyncSessionLocal is not None, "setup_engine() has not run"
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


DbSession = Annotated[AsyncSession, Depends(get_db)]
