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
from app.modules.complaint.infrastructure.orm import Complaint
from app.modules.master.infrastructure.orm import FoodItem, Kitchen, School, Tenant
from app.modules.production.infrastructure.orm import Package, ProductionBatch
from app.modules.traceability.infrastructure.orm import DigitalAsset
from main import create_app

TEST_URL = os.environ.get('FSOS_TEST_DATABASE_URL', '')
CODEC = AccessTokenCodec(SecretStr('alarm-http-test-only-key-at-least-32-bytes'))


@pytest.mark.skipif(not TEST_URL, reason='Migrated test database required')
async def test_school_business_flow():
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
                    await db.execute(insert(School.__table__).values(school_id=foreign, tenant_id=other, kitchen_id=foreign, school_code='FOREIGN', school_name='Foreign'))
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
                    url = '/api/v1/schools'
                    assert (await client.get(url)).status_code == 401
                    pair = (await client.post('/api/v1/auth/login', json={'tenant_id': str(seed_id('tenant')), 'username': 'dev-maintenance', 'password': 'alarm test passphrase'})).json()['data']
                    headers = {'Authorization': f"Bearer {pair['access_token']}"}
                    payload = {'kitchen_id': str(seed_id('kitchen')), 'school_code': 'SCHOOL_HTTP', 'school_name': 'School example', 'student_count': 100, 'latitude': '-6.2', 'longitude': '106.8'}
                    response = await client.post(url, json=payload, headers=headers)
                    assert response.status_code == 201, response.text
                    row = response.json()['data']; sid = row['school_id']
                    assert row['latitude'] == '-6.200000' and 'location' not in row
                    assert row['created_by'] == str(seed_id('actor'))
                    assert response.headers['Cache-Control'] == 'no-store'
                    assert (await client.get(f'{url}/{sid}', headers=headers)).json()['data'] == row
                    assert (await client.post(url, json=payload, headers=headers)).status_code == 409
                    for bad in ({**payload, 'student_count': -1}, {**payload, 'student_count': True}, {**payload, 'longitude': None}, {**payload, 'latitude': '91'}, {**payload, 'tenant_id': str(other)}, {**payload, 'school_name': 'bad\x00'}):
                        assert (await client.post(url, json=bad, headers=headers)).status_code == 400
                    for parent in (foreign, uuid4()):
                        assert (await client.post(url, json={**payload, 'kitchen_id': str(parent)}, headers=headers)).status_code == 409
                    assert (await client.get(f'{url}/{foreign}', headers=headers)).status_code == 404
                    assert (await client.delete(f'{url}/{foreign}', params={'expected_version': 1}, headers=headers)).status_code == 404
                    page = (await client.get(url, params={'kitchen_id': payload['kitchen_id'], 'limit': 1}, headers=headers)).json()['data']
                    assert page['items'][0]['school_id'] == max(sid, str(seed_id('school'))) and page['next_offset'] == 1
                    assert (await client.get(url, params={'kitchen_id': str(foreign)}, headers=headers)).json()['data']['items'] == []
                    assert (await client.get(url, params={'limit': 101}, headers=headers)).status_code == 400
                    changed = await client.put(f'{url}/{sid}', json={**payload, 'school_name': 'Updated', 'expected_version': 1}, headers=headers)
                    assert changed.status_code == 200, changed.text
                    assert changed.json()['data']['version'] == 2
                    assert (await client.put(f'{url}/{sid}', json={**payload, 'expected_version': 1}, headers=headers)).status_code == 409
                    assert (await client.delete(f'{url}/{sid}', params={'expected_version': 1}, headers=headers)).status_code == 409
                    # A historical complaint protects the school from soft deletion.
                    await c.execute(text('RESET ROLE'))
                    food, batch, package, complaint, other_kitchen = (uuid4() for _ in range(5))
                    await c.execute(insert(Kitchen.__table__).values(kitchen_id=other_kitchen, tenant_id=seed_id('tenant'), kitchen_code='OTHER_PARENT', kitchen_name='Other parent'))
                    await c.execute(insert(FoodItem.__table__).values(food_item_id=food, tenant_id=seed_id('tenant'), food_code='TEST_FOOD', food_name='Food', uom='portion'))
                    await c.execute(insert(ProductionBatch.__table__).values(production_batch_id=batch, tenant_id=seed_id('tenant'), kitchen=seed_id('kitchen'), menu=food, batch_code='TEST_BATCH'))
                    await c.execute(insert(Package.__table__).values(package_id=package, tenant_id=seed_id('tenant'), production_batch_id=batch, package_code='TEST_PACKAGE', package_number=1))
                    await c.execute(insert(Complaint.__table__).values(complaint_id=complaint, tenant_id=seed_id('tenant'), package_id=package, school_id=sid, description='Test complaint', reported_at=func.now()))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    assert (await client.put(f'{url}/{sid}', json={**payload, 'kitchen_id': str(other_kitchen), 'expected_version': 2}, headers=headers)).status_code == 409
                    blocked = await client.delete(f'{url}/{sid}', params={'expected_version': 2}, headers=headers)
                    assert blocked.status_code == 409 and blocked.json()['message'] == 'Master record is still referenced'
                    await c.execute(text('RESET ROLE'))
                    await c.execute(update(Complaint.__table__).where(Complaint.complaint_id == complaint).values(deleted_at=func.now()))
                    await c.execute(update(Kitchen.__table__).where(Kitchen.kitchen_id == seed_id('kitchen')).values(status='INACTIVE'))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    assert (await client.put(f'{url}/{sid}', json={**payload, 'expected_version': 2}, headers=headers)).status_code == 409
                    assert (await client.get(f'{url}/{sid}', headers=headers)).status_code == 200
                    # Delete stays available with an inactive parent and without Read/Write permissions.
                    await c.execute(text('RESET ROLE'))
                    readwrite = select(Permission.permission_id).where(Permission.tenant_id == seed_id('tenant'), Permission.permission_code.in_(['School.Read', 'School.Write']))
                    await c.execute(update(RolePermission.__table__).where(RolePermission.permission_id.in_(readwrite)).values(deleted_at=func.now()))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    assert (await client.get(url, headers=headers)).status_code == 403
                    assert (await client.post(url, json={**payload, 'school_code': 'DENIED'}, headers=headers)).status_code == 403
                    deleted = await client.delete(f'{url}/{sid}', params={'expected_version': 2}, headers=headers)
                    assert deleted.status_code == 200, deleted.text
                    data = deleted.json()['data']
                    assert data['version'] == 3 and data['deleted_by'] == str(seed_id('actor'))
                    assert (await client.delete(f'{url}/{sid}', params={'expected_version': 3}, headers=headers)).status_code == 404
                    registry = (await c.execute(select(DigitalAsset.__table__).where(DigitalAsset.entity_uuid == sid))).mappings().one()
                    assert registry['deleted_at'] is not None and registry['name'] == 'Updated'
                    await c.execute(text('RESET ROLE'))
                    await c.execute(update(RolePermission.__table__).where(RolePermission.tenant_id == seed_id('tenant')).values(deleted_at=None))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    assert (await client.get(f'{url}/{sid}', headers=headers)).status_code == 404
                    assert sid not in {r['school_id'] for r in (await client.get(url, headers=headers)).json()['data']['items']}
                    await c.execute(text('RESET ROLE'))
                    delete_permission = select(Permission.permission_id).where(Permission.tenant_id == seed_id('tenant'), Permission.permission_code == 'School.Delete')
                    await c.execute(update(RolePermission.__table__).where(RolePermission.permission_id.in_(delete_permission)).values(deleted_at=func.now()))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    assert (await client.delete(f'{url}/{sid}', params={'expected_version': 3}, headers=headers)).status_code == 403
            finally:
                await outer.rollback()
    finally:
        await engine.dispose()


def test_school_openapi():
    with TestClient(create_app()) as client:
        paths = client.get('/openapi.json').json()['paths']
        for path in ('/api/v1/schools', '/api/v1/schools/{identifier}'):
            for op in paths[path].values():
                assert op['security'] == [{'AccessToken': []}]
                assert '422' not in op['responses']
        assert '201' in paths['/api/v1/schools']['post']['responses']
        assert 'delete' in paths['/api/v1/schools/{identifier}']
