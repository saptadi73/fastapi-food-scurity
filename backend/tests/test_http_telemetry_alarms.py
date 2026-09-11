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
from app.modules.authentication.api import router as auth
from app.modules.authentication.infrastructure.access_tokens import AccessTokenCodec
from app.modules.authentication.infrastructure.orm import Permission, RolePermission, User
from app.modules.authentication.infrastructure.passwords import hash_password_async
from app.modules.master.infrastructure.orm import Device, Tenant
from app.modules.telemetry.infrastructure.orm import AlarmAcknowledgment, AlarmLog
from main import create_app

TEST_URL = os.environ.get('FSOS_TEST_DATABASE_URL', '')
CODEC = AccessTokenCodec(SecretStr('alarm-http-test-only-key-at-least-32-bytes'))


@pytest.mark.skipif(not TEST_URL, reason='Migrated test database required')
async def test_telemetry_alarm_http():
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
                    alarm, imported, future = uuid4(), uuid4(), uuid4()
                    for aid, tenant, device, acknowledged, at in (
                        (alarm, seed_id('tenant'), seed_id('device-public'), False, observed),
                        (imported, seed_id('tenant'), seed_id('device-public'), True, observed),
                        (future, seed_id('tenant'), seed_id('device-public'), False, observed + timedelta(days=1)),
                        (foreign, other, other_device, False, observed),
                    ):
                        await db.execute(insert(AlarmLog.__table__).values(alarm_id=aid, tenant_id=tenant, device_uuid=device, alarm_code='TEST', severity='HIGH', recorded_at=at, acknowledged=acknowledged))
                    for code in ('Alarm.Read', 'Alarm.Acknowledge'):
                        pid = uuid4()
                        await db.execute(insert(Permission.__table__).values(permission_id=pid, tenant_id=seed_id('tenant'), permission_code=code))
                        await db.execute(insert(RolePermission.__table__).values(role_permission_id=uuid4(), tenant_id=seed_id('tenant'), role_id=seed_id('role'), permission_id=pid))
                await provision_runtime_role(c)
                await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                app = create_app()
                app.dependency_overrides[auth.codec_dependency] = lambda: CODEC

                async def test_db():
                    async with factory() as db:
                        yield db

                app.dependency_overrides[auth.database_dependency] = test_db
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                    url = '/api/v1/alarms'
                    assert (await client.get(url)).status_code == 401
                    pair = (await client.post('/api/v1/auth/login', json={'tenant_id': str(seed_id('tenant')), 'username': 'dev-maintenance', 'password': 'alarm test passphrase'})).json()['data']
                    headers = {'Authorization': f"Bearer {pair['access_token']}"}
                    headers = {'Authorization': f"Bearer {pair['access_token']}"}
                    page = await client.get(url, params={'limit': 1}, headers=headers)
                    assert page.status_code == 200, page.text
                    assert page.headers['Cache-Control'] == 'no-store'
                    assert page.json()['data']['next_offset'] == 1
                    for query in ({'limit': 101}, {'acknowledged': '1'}, {'since': '2026-01-01T00:00:00'}, {'since': observed.isoformat(), 'until': observed.isoformat()}, {'device_uuid': 'bad'}):
                        assert (await client.get(url, params=query, headers=headers)).status_code == 400
                    detail = (await client.get(f'{url}/{alarm}', headers=headers)).json()['data']
                    assert detail['effective_acknowledged'] is False
                    assert detail['recorded_at'].endswith('Z')
                    ack_url = f'{url}/{alarm}/acknowledgment'
                    assert (await client.post(ack_url, json={'acknowledged_by': str(other)}, headers=headers)).status_code == 400
                    first = await client.post(ack_url, headers=headers)
                    assert first.status_code == 200, first.text
                    data = first.json()['data']
                    assert data['effective_acknowledged'] is True and data['acknowledged'] is False
                    assert data['acknowledged_by'] == str(seed_id('actor'))
                    assert (await client.post(ack_url, headers=headers)).json()['data'] == data
                    assert (await client.get(f'{url}/{alarm}', headers=headers)).json()['data'] == data
                    imp = (await client.post(f'{url}/{imported}/acknowledgment', headers=headers)).json()['data']
                    assert imp['effective_acknowledged'] and imp['acknowledgment_id'] is None
                    assert (await client.post(f'{url}/{future}/acknowledgment', headers=headers)).status_code == 400
                    page = (await client.get(url, params={'acknowledged': 'true', 'device_uuid': str(seed_id('device-public')), 'since': observed.isoformat(), 'until': (observed + timedelta(hours=1)).isoformat()}, headers=headers)).json()['data']
                    assert {r['alarm_id'] for r in page['items']} == {str(alarm), str(imported)}
                    assert page['next_offset'] is None
                    assert (await client.get(url, params={'offset': 100}, headers=headers)).json()['data']['items'] == []
                    for missing in (foreign, uuid4()):
                        assert (await client.get(f'{url}/{missing}', headers=headers)).status_code == 404
                        assert (await client.post(f'{url}/{missing}/acknowledgment', headers=headers)).status_code == 404
                    await c.execute(text('RESET ROLE'))
                    read_id = await c.scalar(select(Permission.permission_id).where(Permission.tenant_id == seed_id('tenant'), Permission.permission_code == 'Alarm.Read'))
                    await c.execute(update(RolePermission.__table__).where(RolePermission.permission_id == read_id).values(deleted_at=func.now()))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    assert (await client.get(url, headers=headers)).status_code == 403
                    assert (await client.get(f'{url}/{alarm}', headers=headers)).status_code == 403
                    assert (await client.post(ack_url, headers=headers)).status_code == 200
                    await c.execute(text('RESET ROLE'))
                    await c.execute(update(RolePermission.__table__).where(RolePermission.tenant_id == seed_id('tenant')).values(deleted_at=func.now()))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    assert (await client.post(ack_url, headers=headers)).status_code == 403
                    assert await c.scalar(select(func.count()).select_from(AlarmAcknowledgment).where(AlarmAcknowledgment.alarm_id == alarm)) == 1
            finally:
                await outer.rollback()
    finally:
        await engine.dispose()


def test_telemetry_alarm_openapi():
    with TestClient(create_app()) as client:
        paths = client.get('/openapi.json').json()['paths']
        for path in ('/api/v1/alarms', '/api/v1/alarms/{alarm_id}', '/api/v1/alarms/{alarm_id}/acknowledgment'):
            for op in paths[path].values():
                assert op['security'] == [{'AccessToken': []}]
                assert '422' not in op['responses']
                assert '403' in op['responses']
                assert 'requestBody' not in op
