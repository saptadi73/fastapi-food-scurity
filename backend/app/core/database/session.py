from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config.settings import get_settings


class Base(DeclarativeBase):
    """Base ORM; entity domain tetap terpisah dari SQLAlchemy."""


@lru_cache
def get_engine():
    return _create_engine(get_settings().database_url.get_secret_value(), 'DATABASE_URL')


@lru_cache
def get_admin_engine():
    return _create_engine(get_settings().admin_database_url.get_secret_value(), 'ADMIN_DATABASE_URL')


def _create_engine(url: str, setting: str):
    if not url:
        raise RuntimeError(f"Isi {setting} untuk koneksi yang diminta.")
    if not url.startswith("postgresql+asyncpg://"):
        raise ValueError(f"{setting} harus menggunakan postgresql+asyncpg://")
    return create_async_engine(url, pool_pre_ping=True)


async def get_session() -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        # Commit adalah tanggung jawab application service.
        yield session


async def close_database() -> None:
    for factory in (get_engine, get_admin_engine):
        if factory.cache_info().currsize:
            await factory().dispose()
            factory.cache_clear()
