import os
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, insert, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database.development_seed import seed_development, seed_id
from app.core.database.runtime_role import provision_runtime_role
from app.modules.authentication.api import router as auth
from app.modules.authentication.infrastructure.access_tokens import AccessTokenCodec
from app.modules.authentication.infrastructure.orm import Permission, RolePermission, User
from app.modules.authentication.infrastructure.passwords import hash_password_async
from app.modules.master.infrastructure.orm import HoldingRule, HoldingRuleRevision, Tenant
from main import create_app

TEST_URL = os.environ.get('FSOS_TEST_DATABASE_URL', '')
CODEC = AccessTokenCodec(SecretStr('holding-http-test-only-key-at-least-32-bytes'))


@pytest.mark.skipif(not TEST_URL, reason='Migrated test database required')
async def test_holding_http_lifecycle_permissions_and_history():
    assert (make_url(TEST_URL).database or '').startswith('fsos_test')
    engine = create_async_engine(TEST_URL)
    try:
        async with engine.connect() as c:
            outer = await c.begin()
            try:
                factory = async_sessionmaker(bind=c, join_transaction_mode='create_savepoint')
                async with factory() as db, db.begin():
                    await seed_development(db, environment='development')
                    await db.execute(update(User.__table__).where(User.user_id == seed_id('actor')).values(password_hash=await hash_password_async('holding test passphrase')))
                    other, foreign = uuid4(), uuid4()
                    await db.execute(insert(Tenant.__table__).values(tenant_id=other, tenant_code=str(other), tenant_name='Other'))
                    await db.execute(insert(HoldingRule.__table__).values(holding_rule_id=foreign, tenant_id=other, food_category='OTHER', warning_minutes=1, maximum_minutes=2, discard_minutes=3))
                await provision_runtime_role(c)
                await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                app = create_app()
                app.dependency_overrides[auth.codec_dependency] = lambda: CODEC

                async def test_db():
                    async with factory() as db:
                        yield db

                app.dependency_overrides[auth.database_dependency] = test_db
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                    url = '/api/v1/holding-rules'
                    assert (await client.get(url)).status_code == 401
                    pair = (await client.post('/api/v1/auth/login', json={'tenant_id': str(seed_id('tenant')), 'username': 'dev-maintenance', 'password': 'holding test passphrase'})).json()['data']
                    headers = {'Authorization': f"Bearer {pair['access_token']}"}
                    payload = {'food_category': ' HTTP_TEST ', 'warning_minutes': 20, 'maximum_minutes': 30, 'discard_minutes': 40}
                    created = await client.post(url, json=payload, headers=headers)
                    assert created.status_code == 201, created.text
                    assert created.headers['Cache-Control'] == 'no-store'
                    row = created.json()['data']
                    identifier = row['holding_rule_id']
                    assert row['version'] == 1 and row['food_category'] == 'HTTP_TEST'
                    assert row['created_by'] == str(seed_id('actor'))
                    assert (await client.get(f'{url}/{identifier}', headers=headers)).json()['data'] == row
                    assert (await client.post(url, json=payload, headers=headers)).status_code == 409
                    for invalid in ({**payload, 'tenant_id': str(other)}, {**payload, 'warning_minutes': True}, {**payload, 'maximum_minutes': 10}, {**payload, 'discard_minutes': 2147483648}, {**payload, 'food_category': 'bad\x00'}):
                        assert (await client.post(url, json=invalid, headers=headers)).status_code == 400
                    changed = await client.put(f'{url}/{identifier}', json={**payload, 'maximum_minutes': 35, 'expected_version': 1}, headers=headers)
                    assert changed.status_code == 200 and changed.json()['data']['version'] == 2
                    assert (await client.put(f'{url}/{identifier}', json={**payload, 'expected_version': 1}, headers=headers)).status_code == 409
                    history = (await client.get(f'{url}/{identifier}/history', headers=headers)).json()['data']
                    assert [r['version'] for r in history['items']] == [2, 1]
                    assert history['items'][1]['snapshot'] == row
                    assert (await client.get(f'{url}/{identifier}/history?offset=1&limit=1', headers=headers)).json()['data']['items'][0]['version'] == 1
                    listed = (await client.get(f'{url}?limit=1', headers=headers)).json()['data']
                    assert listed['items'][0]['holding_rule_id'] == identifier
                    assert (await client.get(f'{url}?offset=999', headers=headers)).json()['data']['items'] == []
                    assert (await client.get(f'{url}?limit=101', headers=headers)).status_code == 400
                    for missing in (uuid4(), foreign):
                        assert (await client.get(f'{url}/{missing}', headers=headers)).status_code == 404
                        assert (await client.get(f'{url}/{missing}/history', headers=headers)).status_code == 404
                        assert (await client.put(f'{url}/{missing}', json={**payload, 'expected_version': 1}, headers=headers)).status_code == 404
                    await c.execute(text('RESET ROLE'))
                    read_id = await c.scalar(select(Permission.permission_id).where(Permission.tenant_id == seed_id('tenant'), Permission.permission_code == 'HoldingRule.Read'))
                    await c.execute(update(RolePermission.__table__).where(RolePermission.permission_id == read_id).values(deleted_at=func.now()))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    assert (await client.get(url, headers=headers)).status_code == 403
                    assert (await client.get(f'{url}/{identifier}', headers=headers)).status_code == 403
                    assert (await client.post(url, json={**payload, 'food_category': 'WRITE_ONLY'}, headers=headers)).status_code == 201
                    await c.execute(text('RESET ROLE'))
                    await c.execute(update(RolePermission.__table__).where(RolePermission.tenant_id == seed_id('tenant')).values(deleted_at=func.now()))
                    assert (await client.put(f'{url}/{identifier}', json={**payload, 'expected_version': 2}, headers=headers)).status_code == 403
                    assert await c.scalar(select(func.count()).select_from(HoldingRuleRevision).where(HoldingRuleRevision.rule_id == identifier)) == 2
            finally:
                await outer.rollback()
    finally:
        await engine.dispose()


def test_holding_openapi_documents_bearer_and_data():
    with TestClient(create_app()) as client:
        paths = client.get('/openapi.json').json()['paths']
        for path in ('/api/v1/holding-rules', '/api/v1/holding-rules/{rule_id}', '/api/v1/holding-rules/{rule_id}/history'):
            for operation in paths[path].values():
                assert operation['security'] == [{'AccessToken': []}]
                assert '422' not in operation['responses']
                assert '403' in operation['responses']
        assert '201' in paths['/api/v1/holding-rules']['post']['responses']
