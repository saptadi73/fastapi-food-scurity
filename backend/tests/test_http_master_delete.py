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
from app.core.database.supply_permissions import (
    SUPPLY_PERMISSIONS,
    provision_supply_permissions,
)
from app.modules.authentication.api import router as auth
from app.modules.authentication.infrastructure.access_tokens import AccessTokenCodec
from app.modules.authentication.infrastructure.orm import Permission, RolePermission, User
from app.modules.authentication.infrastructure.passwords import hash_password_async
from app.modules.master.infrastructure.orm import (
    Device,
    Kitchen,
    RawMaterial,
    Storage,
    StorageZone,
    Supplier,
    SupplierMaterial,
    Tenant,
)
from app.modules.traceability.infrastructure.orm import DigitalAsset
from main import create_app

TEST_URL = os.environ.get('FSOS_TEST_DATABASE_URL', '')
CODEC = AccessTokenCodec(SecretStr('alarm-http-test-only-key-at-least-32-bytes'))


@pytest.mark.skipif(not TEST_URL, reason='Migrated test database required')
async def test_master_deletion_flow():
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
                    await db.execute(insert(Supplier.__table__).values(supplier_id=foreign, tenant_id=other, supplier_code='FOREIGN', supplier_name='Foreign'))
                    await provision_supply_permissions(db, tenant_id=seed_id('tenant'), actor_id=seed_id('actor'), role_id=seed_id('role'), permissions=list(SUPPLY_PERMISSIONS), environment='development', apply=True)
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
                    url = '/api/v1/suppliers'
                    assert (await client.get(url)).status_code == 401
                    pair = (await client.post('/api/v1/auth/login', json={'tenant_id': str(seed_id('tenant')), 'username': 'dev-maintenance', 'password': 'alarm test passphrase'})).json()['data']
                    headers = {'Authorization': f"Bearer {pair['access_token']}"}
                    async def create(base, payload):
                        result = await client.post(f'/api/v1/{base}', json=payload, headers=headers)
                        assert result.status_code == 201, result.text
                        return result.json()['data']

                    kitchen = await create('kitchens', {'kitchen_code': 'DELETE_K', 'kitchen_name': 'Delete kitchen'})
                    storage = await create('storages', {'kitchen_id': kitchen['kitchen_id'], 'storage_code': 'DELETE_S', 'storage_name': 'Delete storage', 'storage_type': 'DRY_STORAGE'})
                    zone = await create('storage-zones', {'storage_id': storage['storage_id'], 'zone_code': 'DELETE_Z', 'zone_name': 'Delete zone'})
                    supplier = await create('suppliers', {'supplier_code': 'DELETE_P', 'supplier_name': 'Delete supplier'})
                    material = await create('raw-materials', {'material_code': 'DELETE_M', 'material_name': 'Delete material', 'uom': 'kg'})
                    link = await create('supplier-materials', {'supplier_id': supplier['supplier_id'], 'raw_material_id': material['raw_material_id']})
                    resources = [('kitchens', 'kitchen_id', kitchen, Kitchen), ('storages', 'storage_id', storage, Storage),
                                 ('storage-zones', 'zone_id', zone, StorageZone), ('suppliers', 'supplier_id', supplier, Supplier),
                                 ('raw-materials', 'raw_material_id', material, RawMaterial), ('supplier-materials', 'supplier_material_id', link, SupplierMaterial)]
                    for base, key, row, _ in resources:
                        endpoint = f"/api/v1/{base}/{row[key]}"
                        assert (await client.delete(endpoint, headers=headers)).status_code == 400
                        assert (await client.delete(endpoint, params={'expected_version': 0}, headers=headers)).status_code == 400
                        assert (await client.delete(endpoint, params={'expected_version': 2}, headers=headers)).status_code == 409
                        assert (await client.request('DELETE', endpoint, params={'expected_version': 1}, json={}, headers=headers)).status_code == 400
                        assert (await client.delete(f'/api/v1/{base}/{uuid4()}', params={'expected_version': 1}, headers=headers)).status_code == 404
                    assert (await client.delete(f'/api/v1/suppliers/{foreign}', params={'expected_version': 1}, headers=headers)).status_code == 404
                    for base, key, row, _ in (resources[0], resources[1], resources[3], resources[4]):
                        blocked = await client.delete(f"/api/v1/{base}/{row[key]}", params={'expected_version': 1}, headers=headers)
                        assert blocked.status_code == 409 and blocked.json()['message'] == 'Master record is still referenced'
                    # Inactive devices still block zone deletion; delete only after removing the reference.
                    await c.execute(text('RESET ROLE'))
                    device_id = uuid4()
                    await c.execute(insert(Device.__table__).values(device_id=device_id, device_uuid=uuid4(), tenant_id=seed_id('tenant'), zone_id=zone['zone_id'], device_name='Inactive fixture', device_type='TEMPERATURE', status='INACTIVE'))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    assert (await client.delete(f"/api/v1/storage-zones/{zone['zone_id']}", params={'expected_version': 1}, headers=headers)).status_code == 409
                    await c.execute(text('RESET ROLE'))
                    await c.execute(update(Device.__table__).where(Device.device_id == device_id).values(deleted_at=func.now()))
                    # Keep only Delete permissions to prove Read/Write cannot be required implicitly.
                    await c.execute(update(RolePermission.__table__).where(RolePermission.tenant_id == seed_id('tenant'), RolePermission.permission_id.in_(select(Permission.permission_id).where(~Permission.permission_code.endswith('.Delete')))).values(deleted_at=func.now()))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    for index in (2, 1, 0, 5, 3, 4):
                        base, key, row, model = resources[index]
                        endpoint = f"/api/v1/{base}/{row[key]}"
                        deleted = await client.delete(endpoint, params={'expected_version': 1}, headers=headers)
                        assert deleted.status_code == 200, deleted.text
                        data = deleted.json()['data']
                        assert data['version'] == 2 and data['deleted_by'] == str(seed_id('actor'))
                        assert data['deleted_at'].endswith('Z') and data['updated_at'] == data['deleted_at']
                        assert deleted.headers['Cache-Control'] == 'no-store'
                        assert (await client.delete(endpoint, params={'expected_version': 1}, headers=headers)).status_code == 404
                        stored = (await c.execute(select(model.__table__).where(model.__table__.c[key] == row[key]))).mappings().one()
                        assert stored['deleted_at'] is not None  # physical row retained
                        if base in ('kitchens', 'storages', 'suppliers', 'raw-materials'):
                            registry = (await c.execute(select(DigitalAsset.__table__).where(DigitalAsset.entity_uuid == row[key]))).mappings().one()
                            assert registry['deleted_at'] == stored['deleted_at'] and registry['deleted_by'] == seed_id('actor')
                    await c.execute(text('RESET ROLE'))
                    await c.execute(update(RolePermission.__table__).where(RolePermission.tenant_id == seed_id('tenant')).values(deleted_at=None))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    for base, key, row, _ in resources:
                        assert (await client.get(f"/api/v1/{base}/{row[key]}", headers=headers)).status_code == 404
                        page = (await client.get(f'/api/v1/{base}', headers=headers)).json()['data']
                        assert row[key] not in {r[key] for r in page['items']}
                    assert (await client.post('/api/v1/supplier-materials', json={'supplier_id': supplier['supplier_id'], 'raw_material_id': material['raw_material_id']}, headers=headers)).status_code == 409
                    # Revoking Delete blocks the operation even while Write is available.
                    await c.execute(text('RESET ROLE'))
                    await c.execute(update(RolePermission.__table__).where(RolePermission.permission_id.in_(select(Permission.permission_id).where(Permission.tenant_id == seed_id('tenant'), Permission.permission_code.endswith('.Delete')))).values(deleted_at=func.now()))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    for base, key, row, _ in resources:
                        assert (await client.delete(f"/api/v1/{base}/{row[key]}", params={'expected_version': 2}, headers=headers)).status_code == 403
            finally:
                await outer.rollback()
    finally:
        await engine.dispose()


def test_delete_openapi():
    with TestClient(create_app()) as client:
        paths = client.get('/openapi.json').json()['paths']
        for base in ('kitchens', 'storages', 'storage-zones', 'suppliers', 'raw-materials', 'supplier-materials'):
            operation = paths[f'/api/v1/{base}/{{identifier}}']['delete']
            assert operation['security'] == [{'AccessToken': []}]
            assert 'requestBody' not in operation and '422' not in operation['responses']
            assert next(p for p in operation['parameters'] if p['name'] == 'expected_version')['required']
