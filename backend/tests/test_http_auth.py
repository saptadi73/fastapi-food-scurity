import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import delete, insert, select, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.modules.authentication.api import rate_limit, router
from app.modules.authentication.application.session_service import TokenPair
from app.modules.authentication.infrastructure.access_tokens import AccessTokenCodec
from app.modules.authentication.infrastructure.orm import AuthSession, RefreshToken, User
from app.modules.authentication.infrastructure.passwords import hash_password_async
from app.modules.master.infrastructure.orm import Tenant
from main import create_app

TEST_URL = os.environ.get('FSOS_TEST_DATABASE_URL', '')
CODEC = AccessTokenCodec(SecretStr('http-auth-test-only-signing-key-minimum-32-bytes'))
PASSWORD = 'http test passphrase'


@pytest.mark.skipif(not TEST_URL, reason='Migrated test database required')
async def test_http_login_refresh_me_logout_commit_and_isolation():
    assert (make_url(TEST_URL).database or '').startswith('fsos_test')
    engine = create_async_engine(TEST_URL)
    factory = async_sessionmaker(engine)
    tenant, actor = uuid4(), uuid4()
    app = create_app()
    app.dependency_overrides[router.codec_dependency] = lambda: CODEC

    async def test_database():
        async with factory() as db:
            yield db

    app.dependency_overrides[router.database_dependency] = test_database
    try:
        async with factory() as db, db.begin():
            await db.execute(insert(Tenant.__table__).values(tenant_id=tenant, tenant_code=str(tenant), tenant_name='HTTP auth fixture'))
            await db.execute(insert(User.__table__).values(user_id=actor, tenant_id=tenant, username='human', fullname='Test', email='test@example.invalid', status='ACTIVE', password_hash=await hash_password_async(PASSWORD)))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            payload = {'tenant_id': str(tenant), 'username': ' HUMAN ', 'password': PASSWORD}
            assert (await client.get('/api/v1/auth/me')).status_code == 401
            for changed in ({'password': 'wrong passphrase'}, {'tenant_id': str(uuid4())}, {'username': 'missing'}):
                rejected = await client.post('/api/v1/auth/login', json={**payload, **changed})
                assert rejected.status_code == 401 and rejected.json()['data'] is None
                assert rejected.headers['WWW-Authenticate'] == 'Bearer'
            first = await client.post('/api/v1/auth/login', json=payload)
            assert first.status_code == 200 and first.headers['Cache-Control'] == 'no-store'
            assert 'set-cookie' not in first.headers
            pair = first.json()['data']
            assert set(pair) == {'access_token', 'refresh_token', 'expires_in', 'token_type', 'refresh_expires_at'}
            assert pair['expires_in'] == 900 and pair['access_token'] != '**********'
            headers = {'Authorization': f"Bearer {pair['access_token']}"}
            me = await client.get('/api/v1/auth/me', headers=headers)
            assert me.json()['data'] == {'user_id': str(actor), 'tenant_id': str(tenant), 'roles': [], 'permissions': []}
            next_response = await client.post('/api/v1/auth/refresh', json={'refresh_token': pair['refresh_token']})
            assert next_response.status_code == 200
            next_pair = next_response.json()['data']
            assert next_pair['refresh_expires_at'] == pair['refresh_expires_at']
            reused = await client.post('/api/v1/auth/refresh', json={'refresh_token': pair['refresh_token']})
            assert reused.status_code == 401
            assert (await client.get('/api/v1/auth/me', headers={'Authorization': f"Bearer {next_pair['access_token']}"})).status_code == 401
            async with factory() as db:
                family = (await db.execute(select(AuthSession).where(AuthSession.tenant_id == tenant))).scalar_one()
                assert family.revoked_at is not None  # survives the HTTP 401 transaction
            new_pair = (await client.post('/api/v1/auth/login', json=payload)).json()['data']
            for raw in (new_pair['refresh_token'], new_pair['refresh_token'], 'unknown-token'):
                logout = await client.post('/api/v1/auth/logout', json={'refresh_token': raw})
                assert logout.status_code == 200 and logout.json()['data'] == {'logged_out': True}
            assert (await client.get('/api/v1/auth/me', headers={'Authorization': f"Bearer {new_pair['access_token']}"})).status_code == 401
            live_pair = (await client.post('/api/v1/auth/login', json=payload)).json()['data']
            async with factory() as db, db.begin():
                await db.execute(update(User.__table__).where(User.user_id == actor).values(status='INACTIVE'))
            assert (await client.get('/api/v1/auth/me', headers={'Authorization': f"Bearer {live_pair['access_token']}"})).status_code == 401
            assert (await client.post('/api/v1/auth/refresh', json={'refresh_token': live_pair['refresh_token']})).status_code == 401
    finally:
        async with factory() as db, db.begin():
            for model in (RefreshToken, AuthSession, User, Tenant):
                await db.execute(delete(model.__table__).where(model.tenant_id == tenant))
        await engine.dispose()


def test_auth_openapi_validation_and_limiter(monkeypatch):
    app = create_app()
    app.dependency_overrides[router.codec_dependency] = lambda: CODEC

    async def unused_db():
        yield None

    app.dependency_overrides[router.database_dependency] = unused_db
    with TestClient(app) as client:
        schema = client.get('/openapi.json').json()
        login = schema['paths']['/api/v1/auth/login']['post']
        assert '422' not in login['responses'] and '400' in login['responses']
        assert schema['paths']['/api/v1/auth/me']['get']['security'] == [{'AccessToken': []}]
        assert login['responses']['200']['content']['application/json']['schema']['$ref'].endswith('TokensEnvelope')
        invalid = client.post('/api/v1/auth/login', json={'tenant_id': str(uuid4()), 'username': 123, 'password': 'secret-value', 'extra': True})
        assert invalid.status_code == 400 and 'secret-value' not in invalid.text
        assert invalid.headers['Cache-Control'] == 'no-store'
        assert client.post('/api/v1/auth/refresh', json={}).status_code == 400
        app.state.auth_limiter = rate_limit.AuthRateLimiter(limit=1)
        assert client.get('/api/v1/auth/me').status_code == 401
        blocked = client.get('/api/v1/auth/me', headers={'X-Forwarded-For': 'another-address'})
        assert blocked.status_code == 429 and int(blocked.headers['Retry-After']) > 0
        assert blocked.headers['Cache-Control'] == 'no-store'
        assert client.get('/api/v1/health').status_code == 200
    now = [1.0]
    monkeypatch.setattr(rate_limit, 'monotonic', lambda: now[0])
    limiter = rate_limit.AuthRateLimiter(limit=1, window=60, max_clients=1)
    assert limiter.retry_after('a') is None
    assert limiter.retry_after('b') == 60
    now[0] = 61.0
    assert limiter.retry_after('b') is None


def test_auth_missing_configuration_is_sanitized(monkeypatch):
    monkeypatch.setattr(router, 'get_settings', lambda: SimpleNamespace(jwt_secret=SecretStr(''), jwt_access_token_minutes=15, jwt_refresh_token_days=7))
    with TestClient(create_app()) as client:
        response = client.post('/api/v1/auth/login', json={'tenant_id': str(uuid4()), 'username': 'someone', 'password': PASSWORD})
        assert response.status_code == 503 and response.json()['message'] == 'Authentication unavailable'
        assert PASSWORD not in response.text


def test_commit_failure_does_not_deliver_tokens(monkeypatch):
    @asynccontextmanager
    async def failed_commit():
        yield
        raise SQLAlchemyError('private database failure')

    @asynccontextmanager
    async def database():
        yield SimpleNamespace(begin=failed_commit)

    class FakeService:
        def __init__(self, *args):
            pass

        async def login(self, *args):
            return TokenPair(SecretStr('must-not-deliver-access'), SecretStr('must-not-deliver-refresh'), datetime.now(UTC))

    monkeypatch.setattr(router, 'SessionService', FakeService)
    monkeypatch.setattr(router, 'get_engine', lambda: None)
    monkeypatch.setattr(router, 'async_sessionmaker', lambda *args, **kwargs: database)
    app = create_app()
    app.dependency_overrides[router.codec_dependency] = lambda: CODEC
    with TestClient(app) as client:
        result = client.post('/api/v1/auth/login', json={'tenant_id': str(uuid4()), 'username': 'test', 'password': PASSWORD})
        assert result.status_code == 503
        assert 'must-not-deliver' not in result.text and 'private database failure' not in result.text


def test_rate_limit_response_retains_cors(monkeypatch):
    import main
    settings = main.get_settings().model_copy(update={'cors_origins': ['http://frontend.test']})
    monkeypatch.setattr(main, 'get_settings', lambda: settings)
    app = create_app()
    app.state.auth_limiter = rate_limit.AuthRateLimiter(limit=1)
    app.dependency_overrides[router.codec_dependency] = lambda: CODEC
    with TestClient(app) as client:
        headers = {'Origin': 'http://frontend.test'}
        assert client.get('/api/v1/auth/me', headers=headers).status_code == 401
        response = client.get('/api/v1/auth/me', headers=headers)
        assert response.status_code == 429
        assert response.headers['Access-Control-Allow-Origin'] == 'http://frontend.test'
        assert 'Retry-After' in response.headers['Access-Control-Expose-Headers']
        assert client.options('/api/v1/auth/me', headers={**headers, 'Access-Control-Request-Method': 'GET'}).status_code == 200
