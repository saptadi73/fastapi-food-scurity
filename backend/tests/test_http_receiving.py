import os
from datetime import date
from uuid import UUID, uuid4

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import func, insert, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database.development_seed import seed_development, seed_id
from app.core.database.receiving_permissions import (
    RECEIVING_PERMISSIONS,
    provision_receiving_permissions,
)
from app.core.database.runtime_role import provision_runtime_role
from app.core.events.orm import EventLog
from app.modules.authentication.api import router as auth
from app.modules.authentication.infrastructure.access_tokens import AccessTokenCodec
from app.modules.authentication.infrastructure.orm import Permission, RolePermission, User
from app.modules.authentication.infrastructure.passwords import hash_password_async
from app.modules.master.infrastructure.orm import (
    Kitchen,
    Storage,
    Supplier,
    SupplierMaterial,
    Tenant,
)
from app.modules.receiving.infrastructure.orm import RawMaterialBatch
from app.modules.traceability.infrastructure.orm import (
    AssetMovement,
    AssetRelationship,
    DigitalAsset,
)
from main import create_app

TEST_URL = os.environ.get('FSOS_TEST_DATABASE_URL', '')
CODEC = AccessTokenCodec(SecretStr('alarm-http-test-only-key-at-least-32-bytes'))


@pytest.mark.skipif(not TEST_URL, reason='Migrated test database required')
async def test_receiving_business_flow():
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
                    await db.execute(insert(SupplierMaterial.__table__).values(supplier_material_id=uuid4(), tenant_id=seed_id('tenant'), supplier_id=seed_id('supplier'), raw_material_id=seed_id('material')))
                    await provision_receiving_permissions(db, tenant_id=seed_id('tenant'), actor_id=seed_id('actor'), role_id=seed_id('role'), permissions=list(RECEIVING_PERMISSIONS), environment='development', apply=True)
                await provision_runtime_role(c)
                await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                app = create_app()
                app.dependency_overrides[auth.codec_dependency] = lambda: CODEC

                async def test_db():
                    async with factory() as db:
                        yield db

                app.dependency_overrides[auth.database_dependency] = test_db
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                    url = '/api/v1/receivings'
                    assert (await client.get(url)).status_code == 401
                    pair = (await client.post('/api/v1/auth/login', json={'tenant_id': str(seed_id('tenant')), 'username': 'dev-maintenance', 'password': 'alarm test passphrase'})).json()['data']
                    headers = {'Authorization': f"Bearer {pair['access_token']}"}
                    body = {'supplier_id': str(seed_id('supplier')), 'kitchen_id': str(seed_id('kitchen')),
                            'received_at': '2026-01-01T08:00:00+07:00', 'items': [
                                {'raw_material_id': str(seed_id('material')), 'batch_code': 'RECEIPT-OK', 'quantity': '2.500000', 'temperature': '3.20', 'qr_code': 'QR-RB-RECEIPT-OK'},
                                {'raw_material_id': str(seed_id('material')), 'batch_code': 'RECEIPT-REJECT', 'quantity': '1', 'expired_date': '2020-01-01'}]}
                    for bad in ({**body, 'supplier_id': str(foreign)}, {**body, 'kitchen_id': str(uuid4())}):
                        assert (await client.post(url, headers=headers, json=bad)).status_code == 409
                    for bad in ({**body, 'items': []}, {**body, 'received_at': '2026-01-01T08:00:00'}, {**body, 'received_at': '2099-01-01T00:00:00Z'}, {**body, 'operator': str(seed_id('actor'))}):
                        assert (await client.post(url, headers=headers, json=bad)).status_code == 400
                    created = await client.post(url, headers=headers, json=body)
                    assert created.status_code == 201, created.text
                    receipt = created.json()['data']; rid = receipt['receiving_id']
                    assert receipt['received_at'] == '2026-01-01T01:00:00Z'
                    assert receipt['status'] == 'CREATED' and receipt['version'] == 1
                    assert len(receipt['items']) == 2
                    assert all(i['uom'] == 'kg' and i['accepted'] is None for i in receipt['items'])
                    assert created.headers['Cache-Control'] == 'no-store'
                    assert (await client.get(f'{url}/{rid}', headers=headers)).json()['data'] == receipt
                    assert (await client.get(f'{url}/{foreign}', headers=headers)).status_code == 404
                    assert (await client.get(url, params={'supplier_id': str(foreign)}, headers=headers)).json()['data']['items'] == []
                    assert (await client.get(url, params={'limit': 0}, headers=headers)).status_code == 400
                    # Late duplicate after the first new item must roll back header, first batch, registry and event.
                    duplicate = {**body, 'items': [{**body['items'][0], 'batch_code': 'ROLLBACK-BATCH'}, body['items'][0]]}
                    assert (await client.post(url, json=duplicate, headers=headers)).status_code == 409
                    assert not await c.scalar(select(RawMaterialBatch.raw_material_batch_id).where(RawMaterialBatch.batch_code == 'ROLLBACK-BATCH'))
                    decisions = [{'receiving_item_id': i['receiving_item_id'], 'accepted': i['batch']['batch_code'] == 'RECEIPT-OK'} for i in receipt['items']]
                    complete = f'{url}/{rid}/complete'
                    assert (await client.post(complete, headers=headers, json={'expected_version': 1, 'items': decisions[:1]})).status_code == 409
                    assert (await client.post(complete, headers=headers, json={'expected_version': 1, 'items': [{**d, 'accepted': True} for d in decisions]})).status_code == 409
                    assert (await client.post(complete, headers=headers, json={'expected_version': 1, 'items': [{**d, 'accepted': 'false'} for d in decisions]})).status_code == 400
                    response = await client.post(complete, headers=headers, json={'expected_version': 1, 'items': decisions})
                    assert response.status_code == 200, response.text
                    done = response.json()['data']
                    assert done['status'] == 'COMPLETED' and done['version'] == 2
                    assert {i['batch']['status'] for i in done['items']} == {'ACCEPTED', 'REJECTED'}
                    assert all(i['version'] == 2 and i['batch']['version'] == 2 for i in done['items'])
                    assert (await client.post(complete, headers=headers, json={'expected_version': 1, 'items': decisions})).status_code == 409
                    assert (await client.post(f'{url}/{rid}/cancel', headers=headers, json={'expected_version': 2})).status_code == 409
                    accepted = next(i for i in done['items'] if i['accepted'])
                    bid = accepted['raw_material_batch_id']
                    assert accepted['batch']['qr_code'] == 'QR-RB-RECEIPT-OK'
                    resolved = await client.get('/api/v1/raw-material-batches/resolve', headers=headers,
                                                params={'qr_code': ' QR-RB-RECEIPT-OK\n'})
                    assert resolved.status_code == 200 and resolved.json()['data']['raw_material_batch_id'] == bid
                    assert (await client.get(f'/api/v1/raw-material-batches/{bid}', headers=headers)).json()['data'] == accepted['batch']
                    batches = (await client.get('/api/v1/raw-material-batches', headers=headers, params={'receiving_id': rid, 'limit': 1})).json()['data']
                    assert len(batches['items']) == 1 and batches['next_offset'] == 1
                    asset = await c.scalar(select(DigitalAsset.asset_uuid).where(DigitalAsset.entity_uuid == UUID(bid)))
                    assert await c.scalar(select(func.count()).select_from(AssetMovement).where(AssetMovement.asset_uuid == asset)) == 1
                    assert await c.scalar(select(func.count()).select_from(AssetRelationship).where(AssetRelationship.child_uuid == asset)) == 2
                    events = (await c.execute(select(EventLog.event_type, EventLog.payload).where(EventLog.entity_uuid == UUID(rid)))).all()
                    assert {e.event_type for e in events} == {'receiving.created', 'receiving.completed'}
                    assert next(e.payload['receiving'] for e in events if e.event_type == 'receiving.completed') == done
                    stock = f'/api/v1/raw-material-batches/{bid}'
                    balance = (await client.get(stock + '/stock', headers=headers)).json()['data']
                    assert balance['available_quantity'] == '0'
                    assert balance['unallocated_quantity'] == '2.500000'
                    allocation = {'expected_version': 2, 'storage_id': str(seed_id('storage')), 'quantity': '1.5'}
                    rejected_id = next(i['raw_material_batch_id'] for i in done['items'] if not i['accepted'])
                    assert (await client.post(f'/api/v1/raw-material-batches/{rejected_id}/putaway', headers=headers, json=allocation)).status_code == 409
                    await c.execute(text('RESET ROLE'))
                    other_kitchen, wrong_storage, foreign_storage = uuid4(), uuid4(), uuid4()
                    await c.execute(insert(Kitchen).values(kitchen_id=other_kitchen, tenant_id=seed_id('tenant'), kitchen_code='OTHER', kitchen_name='Other'))
                    await c.execute(insert(Storage).values(storage_id=wrong_storage, tenant_id=seed_id('tenant'), kitchen_id=other_kitchen, storage_code='OTHER', storage_name='Other', storage_type='COLD_STORAGE'))
                    foreign_kitchen = uuid4()
                    await c.execute(insert(Kitchen).values(kitchen_id=foreign_kitchen, tenant_id=other, kitchen_code='FOREIGN', kitchen_name='Foreign'))
                    await c.execute(insert(Storage).values(storage_id=foreign_storage, tenant_id=other, kitchen_id=foreign_kitchen, storage_code='FOREIGN', storage_name='Foreign', storage_type='COLD_STORAGE'))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    for sid in (wrong_storage, foreign_storage):
                        assert (await client.post(stock + '/putaway', headers=headers, json={**allocation, 'storage_id': str(sid)})).status_code == 409

                    assert (await client.post(stock + '/putaway', headers=headers, json={**allocation, 'quantity': '3'})).status_code == 409
                    assert (await client.post(stock + '/putaway', headers=headers, json={**allocation, 'storage_id': str(uuid4())})).status_code == 409
                    assert (await client.post(stock + '/putaway', headers=headers, json={**allocation, 'quantity': '-1'})).status_code == 400
                    put = await client.post(stock + '/putaway', headers=headers, json=allocation)
                    assert put.status_code == 201, put.text
                    assert put.json()['data']['batch_version'] == 3
                    assert (await client.post(stock + '/putaway', headers=headers, json=allocation)).status_code == 409
                    remaining = {**allocation, 'expected_version': 3, 'quantity': '1'}
                    assert (await client.post(stock + '/putaway', headers=headers, json=remaining)).status_code == 201
                    balance = (await client.get(stock + '/stock', headers=headers)).json()['data']
                    assert balance['available_quantity'] == '2.500000'
                    assert balance['unallocated_quantity'] == '0.000000'
                    assert balance['version'] == 4
                    assert (await client.post(stock + '/putaway', headers=headers, json={**remaining, 'expected_version': 4})).status_code == 409
                    # Expiry affects availability, without rewriting historical quantities.
                    await c.execute(text('RESET ROLE'))
                    await c.execute(update(RawMaterialBatch).where(RawMaterialBatch.raw_material_batch_id == UUID(bid)).values(expired_date=date(2020, 1, 1)))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    expired = (await client.get(stock + '/stock', headers=headers)).json()['data']
                    assert expired['available_quantity'] == '0' and expired['putaway_quantity'] == '2.500000'
                    assert (await client.post(stock + '/putaway', headers=headers, json={**remaining, 'expected_version': 4})).status_code == 409
                    await c.execute(text('RESET ROLE'))
                    await c.execute(update(RawMaterialBatch).where(RawMaterialBatch.raw_material_batch_id == UUID(bid)).values(expired_date=None))
                    for statement in ('UPDATE stock_entry SET quantity=1', 'DELETE FROM stock_entry', 'TRUNCATE stock_entry'):
                        with pytest.raises(DBAPIError):
                            async with c.begin_nested():
                                await c.execute(text(statement))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    ledger = (await client.get(stock + '/stock-entries', params={'limit': 1}, headers=headers)).json()['data']
                    assert ledger['next_offset'] == 1 and ledger['items'][0]['batch_version'] == 4
                    assert (await client.get(f'/api/v1/raw-material-batches/{foreign}/stock', headers=headers)).status_code == 404
                    assert await c.scalar(select(func.count()).select_from(AssetMovement).where(AssetMovement.asset_uuid == asset)) == 3
                    assert await c.scalar(select(func.count()).select_from(EventLog).where(EventLog.entity_uuid == UUID(bid), EventLog.event_type == 'stock.putaway')) == 2
                    cancelled = await client.post(url, headers=headers, json={**body, 'items': [{**body['items'][0], 'batch_code': 'CANCEL'}]})
                    assert cancelled.status_code == 201, cancelled.text
                    cancel_id = cancelled.json()['data']['receiving_id']
                    cancelled = await client.post(f'{url}/{cancel_id}/cancel', headers=headers, json={'expected_version': 1})
                    assert cancelled.status_code == 200, cancelled.text
                    assert cancelled.json()['data']['items'][0]['batch']['status'] == 'CANCELLED'
                    assert cancelled.json()['data']['items'][0]['accepted'] is None
                    # Existing access token observes revocation; completion grants do not imply reads.
                    await c.execute(text('RESET ROLE'))
                    await c.execute(update(RolePermission.__table__).where(RolePermission.permission_id.in_(select(Permission.permission_id).where(Permission.permission_code == 'Receiving.Read'))).values(deleted_at=func.now()))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    assert (await client.get(f'{url}/{rid}', headers=headers)).status_code == 403
                    assert (await client.get(f'/api/v1/raw-material-batches/{bid}', headers=headers)).status_code == 200
                    await c.execute(text('RESET ROLE'))
                    await c.execute(update(RolePermission).where(RolePermission.permission_id.in_(select(Permission.permission_id).where(Permission.permission_code == 'Stock.Putaway'))).values(deleted_at=func.now()))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    assert (await client.post(stock + '/putaway', headers=headers, json={**remaining, 'expected_version': 4})).status_code == 403
                    assert (await client.get(stock + '/stock', headers=headers)).status_code == 200

            finally:
                await outer.rollback()
    finally:
        await engine.dispose()


def test_receiving_openapi():
    schema = create_app().openapi()
    paths = {p: ops for p, ops in schema['paths'].items() if p.startswith(('/api/v1/receivings', '/api/v1/raw-material-batches'))}
    assert sum(len(ops) for ops in paths.values()) == 14
    for ops in paths.values():
        for operation in ops.values():
            assert '422' not in operation['responses']
            assert '400' in operation['responses']
