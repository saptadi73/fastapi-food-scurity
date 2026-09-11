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
from app.modules.master.infrastructure.orm import AlarmRule, AlarmRuleRevision, Tenant
from main import create_app

TEST_URL = os.environ.get('FSOS_TEST_DATABASE_URL', '')
CODEC = AccessTokenCodec(SecretStr('alarm-http-test-only-key-at-least-32-bytes'))


@pytest.mark.skipif(not TEST_URL, reason='Migrated test database required')
async def test_alarm_http_lifecycle_permissions_and_history():
    assert (make_url(TEST_URL).database or '').startswith('fsos_test')
    engine = create_async_engine(TEST_URL)
    try:
        async with engine.connect() as c:
            outer = await c.begin()
            try:
                factory = async_sessionmaker(bind=c, join_transaction_mode='create_savepoint')
                async with factory() as db, db.begin():
                    await seed_development(db, environment='development')
                    await db.execute(update(User.__table__).where(User.user_id == seed_id('actor')).values(password_hash=await hash_password_async('alarm test passphrase')))
                    other, foreign = uuid4(), uuid4()
                    await db.execute(insert(Tenant.__table__).values(tenant_id=other, tenant_code=str(other), tenant_name='Other'))
                    await db.execute(insert(AlarmRule.__table__).values(alarm_rule_id=foreign, tenant_id=other, rule_code='OTHER', rule_name='Other', rule_category='TEST', priority='HIGH', condition={'field': 'temperature', 'op': 'gt', 'value': 10}, action={'dsl_version': 1, 'steps': [{'type': 'alarm', 'code': 'TEST', 'severity': 'HIGH'}]}))
                await provision_runtime_role(c)
                await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                app = create_app()
                app.dependency_overrides[auth.codec_dependency] = lambda: CODEC

                async def test_db():
                    async with factory() as db:
                        yield db

                app.dependency_overrides[auth.database_dependency] = test_db
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                    url = '/api/v1/alarm-rules'
                    assert (await client.get(url)).status_code == 401
                    pair = (await client.post('/api/v1/auth/login', json={'tenant_id': str(seed_id('tenant')), 'username': 'dev-maintenance', 'password': 'alarm test passphrase'})).json()['data']
                    headers = {'Authorization': f"Bearer {pair['access_token']}"}
                    payload = {'rule_code': ' HTTP_TEST ', 'rule_name': 'Example', 'rule_category': 'TEST', 'priority': 'HIGH', 'condition': {'field': 'temperature', 'op': 'gt', 'value': 10}, 'action': {'dsl_version': 1, 'steps': [{'type': 'alarm', 'code': 'TEST', 'severity': 'HIGH'}]}}
                    created = await client.post(url, json=payload, headers=headers)
                    assert created.status_code == 201, created.text
                    assert created.headers['Cache-Control'] == 'no-store'
                    row = created.json()['data']
                    identifier = row['alarm_rule_id']
                    assert row['version'] == 1 and row['rule_code'] == 'HTTP_TEST'
                    assert row['created_by'] == str(seed_id('actor'))
                    assert (await client.get(f'{url}/{identifier}', headers=headers)).json()['data'] == row
                    assert (await client.post(url, json=payload, headers=headers)).status_code == 409
                    for invalid in ({**payload, 'tenant_id': str(other)}, {**payload, 'enabled': True}, {**payload, 'condition': {'field': 'unknown', 'op': 'gt', 'value': 10}}, {**payload, 'action': {'dsl_version': 1, 'steps': [{'type': 'create_audit', 'code': 'bad\x00'}]}}, {**payload, 'rule_code': 'bad\x00'}):
                        assert (await client.post(url, json=invalid, headers=headers)).status_code == 400
                    changed = await client.put(f'{url}/{identifier}', json={**payload, 'rule_name': 'Updated', 'expected_version': 1}, headers=headers)
                    assert changed.status_code == 200 and changed.json()['data']['version'] == 2
                    assert (await client.put(f'{url}/{identifier}', json={**payload, 'expected_version': 1}, headers=headers)).status_code == 409
                    history = (await client.get(f'{url}/{identifier}/history', headers=headers)).json()['data']
                    assert [r['version'] for r in history['items']] == [2, 1]
                    assert history['items'][1]['snapshot'] == row
                    assert (await client.get(f'{url}/{identifier}/history?offset=1&limit=1', headers=headers)).json()['data']['items'][0]['version'] == 1
                    listed = (await client.get(f'{url}?limit=1', headers=headers)).json()['data']
                    assert listed['items'][0]['alarm_rule_id'] == identifier
                    assert (await client.get(f'{url}?offset=999', headers=headers)).json()['data']['items'] == []
                    assert (await client.get(f'{url}?limit=101', headers=headers)).status_code == 400
                    for missing in (uuid4(), foreign):
                        assert (await client.get(f'{url}/{missing}', headers=headers)).status_code == 404
                        assert (await client.get(f'{url}/{missing}/history', headers=headers)).status_code == 404
                        assert (await client.put(f'{url}/{missing}', json={**payload, 'expected_version': 1}, headers=headers)).status_code == 404
                    assert row['enabled'] is False
                    enabled_url = f'{url}/{identifier}/enabled'
                    for invalid in ({'enabled': 'true', 'expected_version': 2}, {'enabled': True, 'expected_version': True}, {'enabled': True}, {'enabled': True, 'expected_version': 2, 'tenant_id': str(other)}):
                        assert (await client.put(enabled_url, json=invalid, headers=headers)).status_code == 400
                    activated = await client.put(enabled_url, json={'enabled': True, 'expected_version': 2}, headers=headers)
                    assert activated.status_code == 200, activated.text
                    assert activated.json()['data']['version'] == 3
                    assert (await client.put(enabled_url, json={'enabled': True, 'expected_version': 3}, headers=headers)).json()['data'] == activated.json()['data']
                    assert (await client.put(enabled_url, json={'enabled': True, 'expected_version': 2}, headers=headers)).status_code == 409
                    assert (await client.put(f'{url}/{identifier}', json={**payload, 'expected_version': 3}, headers=headers)).status_code == 409
                    disabled = await client.put(enabled_url, json={'enabled': False, 'expected_version': 3}, headers=headers)
                    assert disabled.json()['data']['version'] == 4
                    assert (await client.put(f'{url}/{foreign}/enabled', json={'enabled': True, 'expected_version': 1}, headers=headers)).status_code == 404
                    await c.execute(text('RESET ROLE'))
                    await c.execute(update(AlarmRule.__table__).where(AlarmRule.alarm_rule_id == identifier).values(condition={'legacy': True}, enabled=True))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    legacy = await client.put(enabled_url, json={'enabled': True, 'expected_version': 5}, headers=headers)
                    assert legacy.status_code == 400 and legacy.json()['message'] == 'Invalid alarm rule input'
                    assert (await client.put(enabled_url, json={'enabled': False, 'expected_version': 5}, headers=headers)).json()['data']['version'] == 6
                    await c.execute(text('RESET ROLE'))
                    activate_id = await c.scalar(select(Permission.permission_id).where(Permission.tenant_id == seed_id('tenant'), Permission.permission_code == 'AlarmRule.Activate'))
                    await c.execute(update(RolePermission.__table__).where(RolePermission.permission_id == activate_id).values(deleted_at=func.now()))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    assert (await client.put(enabled_url, json={'enabled': True, 'expected_version': 4}, headers=headers)).status_code == 403
                    assert (await client.get(f'{url}/{identifier}', headers=headers)).status_code == 200
                    await c.execute(text('RESET ROLE'))
                    read_id = await c.scalar(select(Permission.permission_id).where(Permission.tenant_id == seed_id('tenant'), Permission.permission_code == 'AlarmRule.Read'))
                    await c.execute(update(RolePermission.__table__).where(RolePermission.permission_id == read_id).values(deleted_at=func.now()))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    assert (await client.get(url, headers=headers)).status_code == 403
                    assert (await client.get(f'{url}/{identifier}', headers=headers)).status_code == 403
                    write_only = await client.post(url, json={**payload, 'rule_code': 'WRITE_ONLY'}, headers=headers)
                    assert write_only.status_code == 201
                    await c.execute(text('RESET ROLE'))
                    write_id = await c.scalar(select(Permission.permission_id).where(Permission.tenant_id == seed_id('tenant'), Permission.permission_code == 'AlarmRule.Write'))
                    await c.execute(update(RolePermission.__table__).where(RolePermission.permission_id == write_id).values(deleted_at=func.now()))
                    await c.execute(update(RolePermission.__table__).where(RolePermission.permission_id == activate_id).values(deleted_at=None))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    only_url = f"{url}/{write_only.json()['data']['alarm_rule_id']}/enabled"
                    assert (await client.put(only_url, json={'enabled': True, 'expected_version': 1}, headers=headers)).status_code == 200
                    assert (await client.post(url, json={**payload, 'rule_code': 'FORBIDDEN'}, headers=headers)).status_code == 403
                    await c.execute(text('RESET ROLE'))
                    await c.execute(update(RolePermission.__table__).where(RolePermission.tenant_id == seed_id('tenant')).values(deleted_at=func.now()))
                    assert (await client.put(f'{url}/{identifier}', json={**payload, 'expected_version': 2}, headers=headers)).status_code == 403
                    assert await c.scalar(select(func.count()).select_from(AlarmRuleRevision).where(AlarmRuleRevision.rule_id == identifier)) == 6
            finally:
                await outer.rollback()
    finally:
        await engine.dispose()


def test_alarm_openapi_documents_bearer_and_data():
    with TestClient(create_app()) as client:
        paths = client.get('/openapi.json').json()['paths']
        for path in ('/api/v1/alarm-rules', '/api/v1/alarm-rules/{rule_id}', '/api/v1/alarm-rules/{rule_id}/history', '/api/v1/alarm-rules/{rule_id}/enabled'):
            for operation in paths[path].values():
                assert operation['security'] == [{'AccessToken': []}]
                assert '422' not in operation['responses']
                assert '403' in operation['responses']
        assert '201' in paths['/api/v1/alarm-rules']['post']['responses']
