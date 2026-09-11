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
from app.core.database.supply_permissions import (
    SUPPLY_PERMISSIONS,
    provision_supply_permissions,
)
from app.modules.authentication.api import router as auth
from app.modules.authentication.infrastructure.access_tokens import AccessTokenCodec
from app.modules.authentication.infrastructure.orm import Permission, RolePermission, User
from app.modules.authentication.infrastructure.passwords import hash_password_async
from app.modules.master.infrastructure.orm import Supplier, Tenant
from app.modules.traceability.infrastructure.orm import DigitalAsset
from main import create_app

TEST_URL = os.environ.get('FSOS_TEST_DATABASE_URL', '')
CODEC = AccessTokenCodec(SecretStr('alarm-http-test-only-key-at-least-32-bytes'))


@pytest.mark.skipif(not TEST_URL, reason='Migrated test database required')
async def test_supply_business_flow():
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
                    sp = {'supplier_code': 'SAMPLE', 'supplier_name': 'Example supplier', 'email': 'supplier@example.com'}
                    created = await client.post(url, json=sp, headers=headers)
                    assert created.status_code == 201, created.text
                    supplier = created.json()['data']; sid = supplier['supplier_id']
                    assert supplier['version'] == 1 and supplier['created_by'] == str(seed_id('actor'))
                    assert created.headers['Cache-Control'] == 'no-store'
                    assert (await client.get(f'{url}/{sid}', headers=headers)).json()['data'] == supplier
                    assert (await client.post(url, json=sp, headers=headers)).status_code == 409
                    assert (await client.get(f'{url}/{foreign}', headers=headers)).status_code == 404
                    for payload in ({**sp, 'email': 'invalid'}, {**sp, 'supplier_name': 'bad\x00'}, {**sp, 'tenant_id': str(other)}):
                        assert (await client.post(url, json=payload, headers=headers)).status_code == 400
                    mu = '/api/v1/raw-materials'
                    mp = {'material_code': 'MATERIAL', 'material_name': 'Example material', 'uom': 'kg', 'recommended_temperature_min': '1.50', 'recommended_temperature_max': '5.00', 'maximum_storage_hours': '12.50'}
                    created = await client.post(mu, json=mp, headers=headers)
                    assert created.status_code == 201, created.text
                    material = created.json()['data']; mid = material['raw_material_id']
                    assert material['maximum_storage_hours'] == '12.50'
                    for payload in ({**mp, 'uom': ' '}, {**mp, 'maximum_storage_hours': True}, {**mp, 'maximum_storage_hours': '-1'}, {**mp, 'recommended_temperature_min': '10'}, {**mp, 'maximum_storage_hours': '100000000'}):
                        assert (await client.post(mu, json=payload, headers=headers)).status_code == 400
                    lu = '/api/v1/supplier-materials'; lp = {'supplier_id': sid, 'raw_material_id': mid}
                    linked = await client.post(lu, json=lp, headers=headers)
                    assert linked.status_code == 201, linked.text
                    lid = linked.json()['data']['supplier_material_id']
                    assert (await client.post(lu, json=lp, headers=headers)).status_code == 409
                    second = (await client.post(url, json={**sp, 'supplier_code': 'SECOND'}, headers=headers)).json()['data']['supplier_id']
                    assert (await client.post(lu, json={**lp, 'supplier_id': second}, headers=headers)).status_code == 201
                    assert len((await client.get(lu, params={'raw_material_id': mid}, headers=headers)).json()['data']['items']) == 2
                    assert (await client.get(lu, params={'supplier_id': str(foreign)}, headers=headers)).json()['data']['items'] == []
                    for bad in (foreign, uuid4()):
                        assert (await client.post(lu, json={**lp, 'supplier_id': str(bad)}, headers=headers)).status_code == 409
                    for base, ident, payload, field in ((url, sid, sp, 'supplier_name'), (mu, mid, mp, 'material_name')):
                        updated = await client.put(f'{base}/{ident}', json={**payload, field: 'Updated', 'expected_version': 1}, headers=headers)
                        assert updated.status_code == 200, updated.text
                        assert updated.json()['data']['version'] == 2
                        assert (await client.put(f'{base}/{ident}', json={**payload, 'expected_version': 1}, headers=headers)).status_code == 409
                    assert (await client.put(f'{mu}/{mid}', json={**mp, 'uom': 'g', 'expected_version': 2}, headers=headers)).status_code == 409
                    # Pair replacement checks both parents and uniqueness, preserving the previous pair on conflict.
                    assert (await client.put(f'{lu}/{lid}', json={**lp, 'supplier_id': second, 'expected_version': 1}, headers=headers)).status_code == 409
                    replacement = await client.put(f'{lu}/{lid}', json={**lp, 'raw_material_id': str(seed_id('material')), 'expected_version': 1}, headers=headers)
                    assert replacement.status_code == 200, replacement.text
                    assert replacement.json()['data']['version'] == 2
                    assert (await client.get(f'{lu}/{lid}', headers=headers)).json()['data']['raw_material_id'] == str(seed_id('material'))
                    registry = (await c.execute(select(DigitalAsset.__table__).where(DigitalAsset.tenant_id == seed_id('tenant'), DigitalAsset.entity_uuid.in_([sid, mid])))).mappings().all()
                    assert len(registry) == 2 and all(r['name'] == 'Updated' for r in registry)
                    assert (await client.put(f'{url}/{sid}', json={**sp, 'status': 'INACTIVE', 'expected_version': 2}, headers=headers)).status_code == 200
                    assert (await client.post(lu, json=lp, headers=headers)).status_code == 409
                    assert (await client.get(f'{lu}/{lid}', headers=headers)).status_code == 200
                    for base in (url, mu, lu):
                        assert (await client.get(base, params={'limit': 101}, headers=headers)).status_code == 400
                        assert (await client.get(f'{base}/{uuid4()}', headers=headers)).status_code == 404
                        assert (await client.get(base, params={'offset': 999}, headers=headers)).json()['data']['items'] == []
                    await c.execute(text('RESET ROLE'))
                    read_id = await c.scalar(select(Permission.permission_id).where(Permission.tenant_id == seed_id('tenant'), Permission.permission_code == 'Supplier.Read'))
                    await c.execute(update(RolePermission.__table__).where(RolePermission.permission_id == read_id).values(deleted_at=func.now()))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    assert (await client.get(url, headers=headers)).status_code == 403
                    assert (await client.post(url, json={**sp, 'supplier_code': 'WRITE_ONLY'}, headers=headers)).status_code == 201
                    await c.execute(text('RESET ROLE'))
                    await c.execute(update(RolePermission.__table__).where(RolePermission.tenant_id == seed_id('tenant')).values(deleted_at=func.now()))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    assert (await client.post(lu, json=lp, headers=headers)).status_code == 403
            finally:
                await outer.rollback()
    finally:
        await engine.dispose()


def test_supply_openapi():
    with TestClient(create_app()) as client:
        paths = client.get('/openapi.json').json()['paths']
        for base in ('suppliers', 'raw-materials', 'supplier-materials'):
            for path in (f'/api/v1/{base}', f'/api/v1/{base}/{{identifier}}'):
                for op in paths[path].values():
                    assert op['security'] == [{'AccessToken': []}]
                    assert '422' not in op['responses']
            assert '201' in paths[f'/api/v1/{base}']['post']['responses']
