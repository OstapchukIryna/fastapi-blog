"""The engine, the session factory, and the dependency that hands one out.

One engine per process and one session per request. The session is opened
by a FastAPI dependency and closed when the response is finished; nothing
here commits, because deciding when a change is final belongs to the
service performing it.
"""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from blog.core.config import settings

engine = create_async_engine(settings.DATABASE_URL)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Declarative base every model inherits from."""


async def get_db() -> AsyncIterator[AsyncSession]:
    """Open a session for one request and close it afterwards."""
    async with AsyncSessionLocal() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]
