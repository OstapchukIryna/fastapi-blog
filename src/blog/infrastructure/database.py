"""The engine, the session factory, and the dependency that hands one out.

One engine per process and one session per request. The session is opened
by a FastAPI dependency and closed when the response is finished; nothing
here commits, because deciding when a change is final belongs to the
service performing it.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from blog.core.config import settings

HEALTH_CHECK_TIMEOUT_SECONDS = 3

logger = logging.getLogger(__name__)

# * Populated by setup_engine(), not here: tying creation to import rather
# * than to the application's own lifespan makes shutdown a polite fiction
# * — engine.dispose() runs, but nothing ever owned starting it. main.py's
# * lifespan calls setup_engine() before yield and teardown_engine() after,
# * so the pool's lifetime actually matches the app's.
#
# * Module globals rather than app.state or a container class: this
# * process has exactly one engine, and get_db() is a plain function
# * FastAPI calls with no request or app in scope to hang a container
# * off of. app.state exists for values a request can reach through the
# * app object; nothing here is per-app, there is only ever one.
engine: AsyncEngine | None = None
AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None

# * A health check must never share the pool it is reporting on. If the
# * pool is fully checked out, a query through DbSession blocks waiting
# * for a connection to free up instead of answering — the exact moment
# * a load balancer needs a fast 503, this would instead just hang until
# * its own timeout, indistinguishable from a dead backend but slower to
# * notice. NullPool means every check opens its own connection and closes
# * it again; the timeout that keeps an unreachable database from hanging
# * is applied in check_database_alive() itself, not here — see its
# * docstring for why it is not a connect_args value on this engine.
_health_check_engine: AsyncEngine | None = None


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
    global engine, AsyncSessionLocal, _health_check_engine
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    _health_check_engine = create_async_engine(settings.database_url, poolclass=NullPool)


async def teardown_engine() -> None:
    """Dispose the engines and drop the session factory. Called once, from lifespan."""
    global engine, AsyncSessionLocal, _health_check_engine
    if engine is not None:
        await engine.dispose()
    if _health_check_engine is not None:
        await _health_check_engine.dispose()
    engine = None
    AsyncSessionLocal = None
    _health_check_engine = None


async def check_database_alive() -> bool:
    """Whether the database answers, checked on a connection of its own.

    asyncio.timeout() around the whole block, not connect_args on the
    engine: a driver-level connect timeout only bounds the TCP handshake
    — SELECT 1 against a database that accepted the connection but is
    too overloaded to answer it would still hang past
    HEALTH_CHECK_TIMEOUT_SECONDS. It is also spelled differently per
    driver (psycopg wants connect_timeout, asyncpg wants timeout and
    rejects connect_timeout outright), so it silently stops working the
    day DATABASE_URL's driver ever changes. asyncio.timeout() covers
    connect and query alike and does not know or care which driver is
    underneath.

    Returns:
        bool: True if a trivial query succeeded within
            HEALTH_CHECK_TIMEOUT_SECONDS, False for a timeout, a refused
            connection, or any other failure — the caller does not need
            to know which.
    """
    if _health_check_engine is None:
        raise RuntimeError("setup_engine() has not run")
    try:
        async with asyncio.timeout(HEALTH_CHECK_TIMEOUT_SECONDS):
            async with _health_check_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
    except Exception:
        logger.exception("health check could not reach the database")
        return False
    return True


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

    BaseException, not Exception: a client disconnecting mid-request
    surfaces here as asyncio.CancelledError, which deliberately inherits
    from BaseException so that an ordinary `except Exception` does not
    casually swallow a cancellation. That instinct is right for code that
    might otherwise absorb one and keep running — wrong for a
    finally-shaped rollback, which has to run on the way out regardless
    of what is on its way out. The immediate re-raise is what keeps this
    from being "catching too much": nothing here is handled, only cleaned
    up after.
    """
    if AsyncSessionLocal is None:
        raise RuntimeError("setup_engine() has not run")
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except BaseException:
            await session.rollback()
            raise


DbSession = Annotated[AsyncSession, Depends(get_db)]
