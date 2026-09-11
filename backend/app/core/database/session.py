from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config.settings import get_settings


class Base(DeclarativeBase):
    """Base ORM; entity domain tetap terpisah dari SQLAlchemy."""


@lru_cache
def get_engine():
    url = get_settings().database_url.get_secret_value()
    if not url:
        raise RuntimeError("Isi DATABASE_URL di backend/.env terlebih dahulu.")
    if not url.startswith("postgresql+asyncpg://"):
        raise ValueError("DATABASE_URL harus menggunakan postgresql+asyncpg://")
    return create_async_engine(url, pool_pre_ping=True)


async def get_session() -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        # Commit adalah tanggung jawab application service.
        yield session


async def close_database() -> None:
    if get_engine.cache_info().currsize:
        await get_engine().dispose()
        get_engine.cache_clear()
