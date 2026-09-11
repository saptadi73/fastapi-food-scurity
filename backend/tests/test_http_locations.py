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
from app.core.database.location_permissions import (
    LOCATION_PERMISSIONS,
    provision_location_permissions,
)
from app.core.database.runtime_role import provision_runtime_role
from app.modules.authentication.api import router as auth
from app.modules.authentication.infrastructure.access_tokens import AccessTokenCodec
from app.modules.authentication.infrastructure.orm import Permission, RolePermission, User
from app.modules.authentication.infrastructure.passwords import hash_password_async
from app.modules.master.infrastructure.orm import Kitchen, Tenant
from app.modules.traceability.infrastructure.orm import DigitalAsset
from main import create_app

TEST_URL = os.environ.get('FSOS_TEST_DATABASE_URL', '')
CODEC = AccessTokenCodec(SecretStr('alarm-http-test-only-key-at-least-32-bytes'))


@pytest.mark.skipif(not TEST_URL, reason='Migrated test database required')
async def test_locations_business_flow():
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
                    await db.execute(insert(Kitchen.__table__).values(kitchen_id=foreign, tenant_id=other, kitchen_code='FOREIGN', kitchen_name='Foreign'))
                    await provision_location_permissions(db, tenant_id=seed_id('tenant'), actor_id=seed_id('actor'), role_id=seed_id('role'), permissions=list(LOCATION_PERMISSIONS), environment='development', apply=True)
                await provision_runtime_role(c)
                await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                app = create_app()
                app.dependency_overrides[auth.codec_dependency] = lambda: CODEC

                async def test_db():
                    async with factory() as db:
                        yield db

                app.dependency_overrides[auth.database_dependency] = test_db
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                    url = '/api/v1/kitchens'
                    assert (await client.get(url)).status_code == 401
                    pair = (await client.post('/api/v1/auth/login', json={'tenant_id': str(seed_id('tenant')), 'username': 'dev-maintenance', 'password': 'alarm test passphrase'})).json()['data']
                    headers = {'Authorization': f"Bearer {pair['access_token']}"}
                    kp = {'kitchen_code': 'HTTP_K', 'kitchen_name': 'Kitchen', 'latitude': '-6.2', 'longitude': '106.8', 'capacity': 200}
                    created = await client.post(url, json=kp, headers=headers)
                    assert created.status_code == 201, created.text
                    kitchen = created.json()['data']
                    kid = kitchen['kitchen_id']
                    assert kitchen['version'] == 1 and kitchen['created_by'] == str(seed_id('actor'))
                    assert 'location' not in kitchen and kitchen['latitude'] == '-6.200000'
                    assert created.headers['Cache-Control'] == 'no-store'
                    assert (await client.get(f'{url}/{kid}', headers=headers)).json()['data'] == kitchen
                    assert (await client.post(url, json=kp, headers=headers)).status_code == 409
                    assert (await client.get(f'{url}/{foreign}', headers=headers)).status_code == 404
                    for payload in ({**kp, 'tenant_id': str(other)}, {**kp, 'latitude': '91'}, {**kp, 'longitude': None}, {**kp, 'capacity': True}, {**kp, 'kitchen_name': 'bad\x00'}):
                        assert (await client.post(url, json=payload, headers=headers)).status_code == 400
                    su = '/api/v1/storages'
                    sp = {'kitchen_id': kid, 'storage_code': 'COLD', 'storage_name': 'Cold room', 'storage_type': 'COLD_STORAGE', 'temperature_min': '1.50', 'temperature_max': '5.00', 'latitude': '-6.2', 'longitude': '106.8'}
                    storage_response = await client.post(su, json=sp, headers=headers)
                    assert storage_response.status_code == 201, storage_response.text
                    storage = storage_response.json()['data']; sid = storage['storage_id']
                    assert storage['temperature_min'] == '1.50' and storage['latitude'] == '-6.200000'
                    assert (await client.get(su, params={'kitchen_id': kid}, headers=headers)).json()['data']['items'] == [storage]
                    for invalid_parent in (uuid4(), foreign):
                        assert (await client.post(su, json={**sp, 'kitchen_id': str(invalid_parent)}, headers=headers)).status_code == 409
                    assert (await client.post(su, json={**sp, 'temperature_min': '8'}, headers=headers)).status_code == 400
                    zu = '/api/v1/storage-zones'; zp = {'storage_id': sid, 'zone_code': 'RACK_A', 'zone_name': 'Rack A'}
                    zone_response = await client.post(zu, json=zp, headers=headers)
                    assert zone_response.status_code == 201, zone_response.text
                    zone = zone_response.json()['data']; zid = zone['zone_id']
                    for base, ident, payload, name in ((url, kid, kp, 'kitchen_name'), (su, sid, sp, 'storage_name'), (zu, zid, zp, 'zone_name')):
                        changed = await client.put(f'{base}/{ident}', json={**payload, name: 'Updated', 'expected_version': 1}, headers=headers)
                        assert changed.status_code == 200, changed.text
                        assert changed.json()['data']['version'] == 2
                        assert (await client.put(f'{base}/{ident}', json={**payload, 'expected_version': 1}, headers=headers)).status_code == 409
                        assert (await client.get(base, params={'limit': 101}, headers=headers)).status_code == 400
                        assert (await client.get(f'{base}/{uuid4()}', headers=headers)).status_code == 404
                    # An existing different active parent cannot be substituted.
                    assert (await client.put(f'{su}/{sid}', json={**sp, 'kitchen_id': str(seed_id('kitchen')), 'expected_version': 2}, headers=headers)).status_code == 409
                    registry = (await c.execute(select(DigitalAsset.__table__).where(DigitalAsset.tenant_id == seed_id('tenant'), DigitalAsset.entity_uuid.in_([kid, sid])))).mappings().all()
                    assert len(registry) == 2 and all(r['name'] == 'Updated' for r in registry)
                    # Inactive kitchen blocks child writes; historical reads remain available.
                    assert (await client.put(f'{url}/{kid}', json={**kp, 'status': 'INACTIVE', 'expected_version': 2}, headers=headers)).status_code == 200
                    assert (await client.post(zu, json={**zp, 'zone_code': 'BLOCKED'}, headers=headers)).status_code == 409
                    assert (await client.get(f'{zu}/{zid}', headers=headers)).status_code == 200
                    await c.execute(text('RESET ROLE'))
                    read_id = await c.scalar(select(Permission.permission_id).where(Permission.tenant_id == seed_id('tenant'), Permission.permission_code == 'Kitchen.Read'))
                    await c.execute(update(RolePermission.__table__).where(RolePermission.permission_id == read_id).values(deleted_at=func.now()))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    assert (await client.get(url, headers=headers)).status_code == 403
                    assert (await client.post(url, json={**kp, 'kitchen_code': 'WRITE_ONLY'}, headers=headers)).status_code == 201
                    await c.execute(text('RESET ROLE'))
                    await c.execute(update(RolePermission.__table__).where(RolePermission.tenant_id == seed_id('tenant')).values(deleted_at=func.now()))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    assert (await client.post(url, json={**kp, 'kitchen_code': 'DENIED'}, headers=headers)).status_code == 403
            finally:
                await outer.rollback()
    finally:
        await engine.dispose()


def test_location_openapi():
    with TestClient(create_app()) as client:
        paths = client.get('/openapi.json').json()['paths']
        for base in ('kitchens', 'storages', 'storage-zones'):
            for path in (f'/api/v1/{base}', f'/api/v1/{base}/{{identifier}}'):
                for op in paths[path].values():
                    assert op['security'] == [{'AccessToken': []}]
                    assert '422' not in op['responses']
            assert '201' in paths[f'/api/v1/{base}']['post']['responses']
