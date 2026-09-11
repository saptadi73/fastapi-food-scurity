from unittest.mock import AsyncMock

import pytest
from pydantic import SecretStr

from app.core.config.settings import Settings
from app.core.database import session as database


async def test_separate_pools_and_disposal(monkeypatch):
    settings = Settings(_env_file=None, database_url=SecretStr('postgresql+asyncpg://runtime@localhost/fsos'),
                        admin_database_url=SecretStr('postgresql+asyncpg://owner@localhost/fsos'))
    monkeypatch.setattr(database, 'get_settings', lambda: settings)
    calls = []

    def engine(url, **kwargs):
        result = AsyncMock()
        calls.append((url, result))
        return result

    database.get_engine.cache_clear()
    database.get_admin_engine.cache_clear()
    monkeypatch.setattr(database, 'create_async_engine', engine)
    assert database.get_engine() is database.get_engine()
    assert database.get_admin_engine() is database.get_admin_engine()
    assert database.get_engine() is not database.get_admin_engine()
    assert [url for url, _ in calls] == [settings.database_url.get_secret_value(), settings.admin_database_url.get_secret_value()]
    await database.close_database()
    for _, pool in calls:
        pool.dispose.assert_awaited_once()
    assert database.get_engine.cache_info().currsize == database.get_admin_engine.cache_info().currsize == 0


def test_missing_admin_does_not_fall_back_to_runtime(monkeypatch):
    settings = Settings(_env_file=None, database_url=SecretStr('postgresql+asyncpg://runtime@localhost/fsos'), admin_database_url=SecretStr(''))
    monkeypatch.setattr(database, 'get_settings', lambda: settings)
    database.get_admin_engine.cache_clear()
    with pytest.raises(RuntimeError, match='ADMIN_DATABASE_URL'):
        database.get_admin_engine()
