import os
from datetime import UTC, datetime, timedelta
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
from app.core.database.telemetry_permissions import provision_telemetry_permissions
from app.modules.authentication.api import router as auth
from app.modules.authentication.infrastructure.access_tokens import AccessTokenCodec
from app.modules.authentication.infrastructure.orm import Permission, RolePermission, User
from app.modules.authentication.infrastructure.passwords import hash_password_async
from app.modules.master.infrastructure.orm import Device, Tenant
from app.modules.telemetry.infrastructure.orm import DeviceSession, DeviceSessionEnd
from main import create_app

TEST_URL = os.environ.get('FSOS_TEST_DATABASE_URL', '')
CODEC = AccessTokenCodec(SecretStr('alarm-http-test-only-key-at-least-32-bytes'))


@pytest.mark.skipif(not TEST_URL, reason='Migrated test database required')
async def test_device_session_http():
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
                    other_device = uuid4()
                    await db.execute(insert(Device.__table__).values(device_id=uuid4(), tenant_id=other, device_uuid=other_device, device_name='Other', device_type='TEMPERATURE'))
                    observed = datetime.now(UTC) - timedelta(hours=2)
                    session_id, imported = uuid4(), uuid4()
                    ended = observed + timedelta(hours=1)
                    for sid, tenant, device, end in (
                        (session_id, seed_id('tenant'), seed_id('device-public'), None),
                        (imported, seed_id('tenant'), seed_id('device-public'), ended),
                        (foreign, other, other_device, None),
                    ):
                        await db.execute(insert(DeviceSession.__table__).values(session_id=sid, tenant_id=tenant, device_uuid=device, connected_at=observed, disconnected_at=end, recorded_at=observed, ip_address='192.0.2.1', firmware='test'))
                    await provision_telemetry_permissions(db, tenant_id=seed_id('tenant'), actor_id=seed_id('actor'), role_id=seed_id('role'), permissions=['DeviceSession.Read', 'DeviceSession.Close'], environment='development', apply=True)
                await provision_runtime_role(c)
                await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                app = create_app()
                app.dependency_overrides[auth.codec_dependency] = lambda: CODEC

                async def test_db():
                    async with factory() as db:
                        yield db

                app.dependency_overrides[auth.database_dependency] = test_db
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                    url = '/api/v1/device-sessions'
                    assert (await client.get(url)).status_code == 401
                    pair = (await client.post('/api/v1/auth/login', json={'tenant_id': str(seed_id('tenant')), 'username': 'dev-maintenance', 'password': 'alarm test passphrase'})).json()['data']
                    headers = {'Authorization': f"Bearer {pair['access_token']}"}
                    detail = await client.get(f'{url}/{session_id}', headers=headers)
                    assert detail.status_code == 200, detail.text
                    row = detail.json()['data']
                    assert row['is_open'] and row['ip_address'] == '192.0.2.1'
                    assert detail.headers['Cache-Control'] == 'no-store'
                    page = (await client.get(url, params={'limit': 1}, headers=headers)).json()['data']
                    assert page['next_offset'] == 1
                    for query in ({'limit': 101}, {'is_open': '1'}, {'since': '2026-01-01T00:00:00'}, {'since': observed.isoformat(), 'until': observed.isoformat()}):
                        assert (await client.get(url, params=query, headers=headers)).status_code == 400
                    end_url = f'{url}/{session_id}/end'
                    for payload in ({}, {'disconnected_at': None}, {'disconnected_at': 123}, {'disconnected_at': '2026-01-01T00:00:00'}, {'disconnected_at': ended.isoformat(), 'tenant_id': str(other)}, {'disconnected_at': (observed - timedelta(seconds=1)).isoformat()}, {'disconnected_at': (observed + timedelta(days=1)).isoformat()}):
                        assert (await client.post(end_url, json=payload, headers=headers)).status_code == 400
                    payload = {'disconnected_at': ended.isoformat()}
                    first = await client.post(end_url, json=payload, headers=headers)
                    assert first.status_code == 200, first.text
                    data = first.json()['data']
                    assert data['is_open'] is False and data['disconnected_at'] is None
                    assert data['effective_disconnected_at'].endswith('Z') and data['session_end_id']
                    assert (await client.post(end_url, json=payload, headers=headers)).json()['data'] == data
                    assert (await client.get(f'{url}/{session_id}', headers=headers)).json()['data'] == data
                    assert (await client.post(end_url, json={'disconnected_at': (ended + timedelta(seconds=1)).isoformat()}, headers=headers)).status_code == 409
                    imp = (await client.post(f'{url}/{imported}/end', json=payload, headers=headers)).json()['data']
                    assert imp['session_end_id'] is None and imp['is_open'] is False
                    page = (await client.get(url, params={'is_open': 'false', 'device_uuid': str(seed_id('device-public')), 'since': observed.isoformat(), 'until': ended.isoformat()}, headers=headers)).json()['data']
                    assert {r['session_id'] for r in page['items']} == {str(session_id), str(imported)}
                    assert page['next_offset'] is None
                    assert (await client.get(url, params={'is_open': 'true'}, headers=headers)).json()['data']['items'] == []
                    for missing in (foreign, uuid4()):
                        assert (await client.get(f'{url}/{missing}', headers=headers)).status_code == 404
                        assert (await client.post(f'{url}/{missing}/end', json=payload, headers=headers)).status_code == 404
                    await c.execute(text('RESET ROLE'))
                    read_id = await c.scalar(select(Permission.permission_id).where(Permission.tenant_id == seed_id('tenant'), Permission.permission_code == 'DeviceSession.Read'))
                    await c.execute(update(RolePermission.__table__).where(RolePermission.permission_id == read_id).values(deleted_at=func.now()))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    assert (await client.get(url, headers=headers)).status_code == 403
                    assert (await client.get(f'{url}/{session_id}', headers=headers)).status_code == 403
                    assert (await client.post(end_url, json=payload, headers=headers)).status_code == 200
                    await c.execute(text('RESET ROLE'))
                    await c.execute(update(RolePermission.__table__).where(RolePermission.tenant_id == seed_id('tenant')).values(deleted_at=func.now()))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    assert (await client.post(end_url, json=payload, headers=headers)).status_code == 403
                    assert await c.scalar(select(func.count()).select_from(DeviceSessionEnd).where(DeviceSessionEnd.session_id == session_id)) == 1
                    assert await c.scalar(select(DeviceSessionEnd.created_by).where(DeviceSessionEnd.session_id == session_id)) == seed_id('actor')
            finally:
                await outer.rollback()
    finally:
        await engine.dispose()


def test_device_session_openapi():
    with TestClient(create_app()) as client:
        paths = client.get('/openapi.json').json()['paths']
        for path in ('/api/v1/device-sessions', '/api/v1/device-sessions/{session_id}', '/api/v1/device-sessions/{session_id}/end'):
            for op in paths[path].values():
                assert op['security'] == [{'AccessToken': []}]
                assert '422' not in op['responses'] and '403' in op['responses']
        assert paths['/api/v1/device-sessions/{session_id}/end']['post']['requestBody']['required']
