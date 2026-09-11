import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

import main
from app.core.database import readiness


@pytest.mark.parametrize(
    ('checks', 'status'),
    [({'postgresql': 'ok', 'extensions': 'ok', 'schema': 'ok'}, 200),
     ({'postgresql': 'unavailable', 'extensions': 'unchecked', 'schema': 'unchecked'}, 503),
     ({'postgresql': 'ok', 'extensions': 'missing', 'schema': 'ok'}, 503),
     ({'postgresql': 'ok', 'extensions': 'ok', 'schema': 'mismatch'}, 503)],
)
def test_readiness_http(monkeypatch, checks, status):
    probe = AsyncMock(return_value=checks)
    monkeypatch.setattr(main, 'check_readiness', probe)
    with TestClient(main.create_app()) as client:
        assert client.get('/api/v1/health').status_code == 200
        probe.assert_not_awaited()
        response = client.get('/api/v1/ready')
        assert response.status_code == status
        body = response.json()
        assert body['success'] is (status == 200)
        assert body['code'] == status
        assert body['data']['checks'] == checks
        assert body['meta']['request_id'] == response.headers['X-Request-ID']
        assert response.headers['Cache-Control'] == 'no-store'
        assert '503' in client.get('/openapi.json').json()['paths']['/api/v1/ready']['get']['responses']


@pytest.mark.parametrize(
    ('version', 'extensions', 'migrated', 'revisions', 'expected'),
    [(180000, ['postgis', 'pgcrypto'], True, ['head-a', 'head-b'], ('ok', 'ok', 'ok')),
     (170000, ['postgis'], True, ['old'], ('unsupported', 'missing', 'mismatch')),
     (180000, ['postgis', 'pgcrypto'], False, [], ('ok', 'ok', 'mismatch')),
     (180000, ['postgis', 'pgcrypto'], True, ['head-a'], ('ok', 'ok', 'mismatch'))],
)
async def test_database_checks(monkeypatch, version, extensions, migrated, revisions, expected):
    connection = SimpleNamespace(
        scalar=AsyncMock(side_effect=[version, migrated]),
        execute=AsyncMock(side_effect=[Mock(scalars=lambda: extensions), Mock(scalars=lambda: revisions)]),
    )
    closed = []

    @asynccontextmanager
    async def connect():
        try:
            yield connection
        finally:
            closed.append(True)

    monkeypatch.setattr(readiness, 'get_engine', lambda: SimpleNamespace(connect=connect))
    monkeypatch.setattr(readiness, 'expected_revisions', lambda: {'head-a', 'head-b'})
    checks = await readiness.check_readiness()
    assert tuple(checks.values()) == expected
    assert closed == [True]
    assert connection.execute.await_count == (2 if migrated else 1)


@pytest.mark.parametrize('slow', [False, True])
async def test_probe_failure_and_timeout_are_sanitized(monkeypatch, slow):
    closed = []

    @asynccontextmanager
    async def connect():
        try:
            if slow:
                await asyncio.sleep(10)
            raise RuntimeError('postgresql://private-password@private-host/database')
            yield  # pragma: no cover - async context manager protocol
        finally:
            closed.append(True)

    monkeypatch.setattr(readiness, 'get_engine', lambda: SimpleNamespace(connect=connect))
    monkeypatch.setattr(readiness, 'get_settings', lambda: SimpleNamespace(readiness_timeout_seconds=0.01))
    result = await readiness.check_readiness()
    assert result == {'postgresql': 'timeout' if slow else 'unavailable',
                      'extensions': 'unchecked', 'schema': 'unchecked'}
    assert closed == [True]


def test_expected_heads_loaded_from_project(monkeypatch, tmp_path):
    heads = readiness.expected_revisions()
    assert heads
    monkeypatch.chdir(tmp_path)
    readiness.expected_revisions.cache_clear()
    assert readiness.expected_revisions() == heads
