import os
from uuid import UUID, uuid4

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
from app.modules.fleet.infrastructure.orm import Delivery
from app.modules.master.infrastructure.orm import Device, Driver, Tenant, Vehicle
from app.modules.traceability.infrastructure.orm import DigitalAsset
from main import create_app

TEST_URL = os.environ.get('FSOS_TEST_DATABASE_URL', '')
CODEC = AccessTokenCodec(SecretStr('alarm-http-test-only-key-at-least-32-bytes'))


@pytest.mark.skipif(not TEST_URL, reason='Migrated test database required')
async def test_vehicle_driver_flow():
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
                    await db.execute(insert(Driver.__table__).values(driver_id=foreign, tenant_id=other, driver_code='FOREIGN', driver_name='Foreign'))
                    gps_id, gps_public = uuid4(), uuid4()
                    await db.execute(insert(Device.__table__).values(device_id=gps_id, device_uuid=gps_public, tenant_id=seed_id('tenant'), device_name='GPS fixture', device_type='GPS', status='ACTIVE'))
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
                    url = '/api/v1/drivers'
                    assert (await client.get(url)).status_code == 401
                    pair = (await client.post('/api/v1/auth/login', json={'tenant_id': str(seed_id('tenant')), 'username': 'dev-maintenance', 'password': 'alarm test passphrase'})).json()['data']
                    headers = {'Authorization': f"Bearer {pair['access_token']}"}
                    dp = {'driver_code': 'DRIVER_TEST', 'driver_name': 'Driver example'}
                    created = await client.post(url, json=dp, headers=headers)
                    assert created.status_code == 201, created.text
                    driver = created.json()['data']; did = driver['driver_id']
                    assert driver['version'] == 1 and driver['created_by'] == str(seed_id('actor'))
                    assert (await client.post(url, json=dp, headers=headers)).status_code == 409
                    assert (await client.get(f'{url}/{foreign}', headers=headers)).status_code == 404
                    assert (await client.delete(f'{url}/{foreign}', params={'expected_version': 1}, headers=headers)).status_code == 404
                    vu = '/api/v1/vehicles'
                    vp = {'vehicle_code': 'V_TEST', 'plate_number': 'TEST-001', 'vehicle_type': 'VAN', 'capacity': '100.50', 'driver_id': did, 'gps_device': str(gps_id), 'latitude': '-6.2', 'longitude': '106.8'}
                    result = await client.post(vu, json=vp, headers=headers)
                    assert result.status_code == 201, result.text
                    vehicle = result.json()['data']; vid = vehicle['vehicle_id']
                    assert vehicle['latitude'] == '-6.200000' and vehicle['capacity'] == '100.50'
                    assert result.headers['Cache-Control'] == 'no-store'
                    assert (await client.get(f'{vu}/{vid}', headers=headers)).json()['data'] == vehicle
                    assert (await client.get(vu, params={'driver_id': did}, headers=headers)).json()['data']['items'] == [vehicle]
                    for wrong in ({**vp, 'capacity': True}, {**vp, 'capacity': '-1'}, {**vp, 'capacity': '10000000000'}, {**vp, 'longitude': None}, {**vp, 'latitude': '91'}, {**vp, 'plate_number': 'bad\x00'}, {**vp, 'tenant_id': str(other)}):
                        assert (await client.post(vu, json=wrong, headers=headers)).status_code == 400
                    for wrong in ({**vp, 'driver_id': str(foreign)}, {**vp, 'gps_device': str(gps_public)}, {**vp, 'gps_device': str(seed_id('device'))}):
                        assert (await client.post(vu, json=wrong, headers=headers)).status_code == 409
                    assert (await client.post(vu, json={**vp, 'vehicle_code': 'DIFFERENT'}, headers=headers)).status_code == 409
                    assert (await client.delete(f'{url}/{did}', params={'expected_version': 1}, headers=headers)).status_code == 409
                    # Existing delivery protects both master records, even after it has completed.
                    await c.execute(text('RESET ROLE'))
                    delivery = uuid4()
                    await c.execute(insert(Delivery.__table__).values(delivery_id=delivery, tenant_id=seed_id('tenant'), vehicle=vid, driver=did, status='COMPLETED'))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    assert (await client.delete(f'{vu}/{vid}', params={'expected_version': 1}, headers=headers)).status_code == 409
                    updated = await client.put(f'{url}/{did}', json={**dp, 'status': 'INACTIVE', 'expected_version': 1}, headers=headers)
                    assert updated.status_code == 200 and updated.json()['data']['version'] == 2
                    assert (await client.put(f'{vu}/{vid}', json={**vp, 'expected_version': 1}, headers=headers)).status_code == 409
                    # Clear optional links explicitly; historical delivery driver remains unchanged.
                    unlinked = {**vp, 'driver_id': None, 'gps_device': None, 'plate_number': 'TEST-UPDATED'}
                    changed = await client.put(f'{vu}/{vid}', json={**unlinked, 'expected_version': 1}, headers=headers)
                    assert changed.status_code == 200, changed.text
                    assert changed.json()['data']['version'] == 2
                    assert await c.scalar(select(Delivery.driver).where(Delivery.delivery_id == delivery)) == UUID(did)
                    assert (await client.put(f'{vu}/{vid}', json={**unlinked, 'expected_version': 1}, headers=headers)).status_code == 409
                    registry = (await c.execute(select(DigitalAsset.__table__).where(DigitalAsset.entity_uuid == vid))).mappings().one()
                    assert registry['name'] == 'TEST-UPDATED'
                    assert (await client.delete(f'{url}/{did}', params={'expected_version': 2}, headers=headers)).status_code == 409
                    await c.execute(text('RESET ROLE'))
                    await c.execute(update(Delivery.__table__).where(Delivery.delivery_id == delivery).values(deleted_at=func.now()))
                    rw = select(Permission.permission_id).where(Permission.tenant_id == seed_id('tenant'), Permission.permission_code.in_(['Driver.Read','Driver.Write','Vehicle.Read','Vehicle.Write']))
                    await c.execute(update(RolePermission.__table__).where(RolePermission.permission_id.in_(rw)).values(deleted_at=func.now()))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    for base, ident in ((url,did),(vu,vid)):
                        assert (await client.get(base, headers=headers)).status_code == 403
                        deleted = await client.delete(f'{base}/{ident}', params={'expected_version': 2}, headers=headers)
                        assert deleted.status_code == 200, deleted.text
                        assert deleted.json()['data']['version'] == 3 and deleted.json()['data']['deleted_by'] == str(seed_id('actor'))
                        assert (await client.delete(f'{base}/{ident}', params={'expected_version': 3}, headers=headers)).status_code == 404
                    stored = await c.scalar(select(Vehicle.deleted_at).where(Vehicle.vehicle_id == vid))
                    assert stored is not None
                    assert await c.scalar(select(DigitalAsset.deleted_at).where(DigitalAsset.entity_uuid == vid)) == stored
                    await c.execute(text('RESET ROLE'))
                    await c.execute(update(RolePermission.__table__).where(RolePermission.tenant_id == seed_id('tenant')).values(deleted_at=None))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    for base, ident in ((url,did),(vu,vid)):
                        assert (await client.get(f'{base}/{ident}', headers=headers)).status_code == 404
                        assert (await client.get(base, params={'limit': 101}, headers=headers)).status_code == 400
                    await c.execute(text('RESET ROLE'))
                    deletes = select(Permission.permission_id).where(Permission.tenant_id == seed_id('tenant'), Permission.permission_code.in_(['Driver.Delete','Vehicle.Delete']))
                    await c.execute(update(RolePermission.__table__).where(RolePermission.permission_id.in_(deletes)).values(deleted_at=func.now()))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    assert (await client.delete(f'{vu}/{vid}', params={'expected_version': 3}, headers=headers)).status_code == 403
            finally:
                await outer.rollback()
    finally:
        await engine.dispose()


def test_fleet_master_openapi():
    with TestClient(create_app()) as client:
        paths = client.get('/openapi.json').json()['paths']
        for base in ('drivers','vehicles'):
            for path in (f'/api/v1/{base}', f'/api/v1/{base}/{{identifier}}'):
                for op in paths[path].values():
                    assert op['security'] == [{'AccessToken': []}]
                    assert '422' not in op['responses']
            assert 'delete' in paths[f'/api/v1/{base}/{{identifier}}']
