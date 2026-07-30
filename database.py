import os
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# Адрес базы берётся из окружения, потому что blog.db лежит в репозитории:
# любой автоматический прогон по API писал бы в отслеживаемый файл и оставлял
# после себя diff. Значение по умолчанию — прежнее, так что обычный запуск
# ничего не замечает.
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./blog.db")

engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


# Один псевдоним на весь проект. Раньше эта строка стояла пятью
# одинаковыми копиями — в каждом роутере, в auth и в main; сессия у
# приложения одна, и объявлять её заново на каждый модуль значило дать
# пяти копиям возможность разойтись.
DbSession = Annotated[AsyncSession, Depends(get_db)]
