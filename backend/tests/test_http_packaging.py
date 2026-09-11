import os
from uuid import UUID, uuid4

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import func, insert, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database.development_seed import seed_development, seed_id
from app.core.database.receiving_permissions import (
    RECEIVING_PERMISSIONS,
    provision_receiving_permissions,
)
from app.core.database.runtime_role import provision_runtime_role
from app.core.database.supply_permissions import provision_supply_permissions
from app.core.events.orm import EventLog
from app.modules.authentication.api import router as auth
from app.modules.authentication.infrastructure.access_tokens import AccessTokenCodec
from app.modules.authentication.infrastructure.orm import Permission, RolePermission, User
from app.modules.authentication.infrastructure.passwords import hash_password_async
from app.modules.master.infrastructure.orm import (
    FoodItem,
    HoldingRule,
    Kitchen,
    Recipe,
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
async def test_packaging_business_flow():
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
                async with factory() as db, db.begin():
                    await provision_supply_permissions(db, tenant_id=seed_id('tenant'), actor_id=seed_id('actor'), role_id=seed_id('role'), permissions=['PackagingType.Read', 'PackagingType.Write', 'PackagingType.Delete'], environment='development', apply=True)
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
                                {'raw_material_id': str(seed_id('material')), 'batch_code': 'RECEIPT-OK', 'quantity': '2.500000', 'temperature': '3.20'},
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
                    await c.execute(text('RESET ROLE'))
                    menu = uuid4()
                    await c.execute(insert(FoodItem).values(food_item_id=menu, tenant_id=seed_id('tenant'), food_code='PROD-MENU', food_name='Production menu', uom='portion', holding_limit_minutes=60, category='PACKAGING_TEST'))
                    recipe_id = uuid4()
                    await c.execute(insert(Recipe).values(recipe_id=recipe_id, tenant_id=seed_id('tenant'), food_item_id=menu, raw_material_id=seed_id('material'), quantity='0.25', uom='kg'))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    production = '/api/v1/production-batches'
                    body_prod = {'batch_code': 'PROD-001', 'kitchen': str(seed_id('kitchen')), 'menu': str(menu), 'planned_quantity': '4'}
                    assert (await client.post(production, headers=headers, json={**body_prod, 'menu': str(foreign)})).status_code == 409
                    assert (await client.post(production, headers=headers, json={**body_prod, 'planned_quantity': True})).status_code == 400
                    made = await client.post(production, headers=headers, json=body_prod)
                    assert made.status_code == 201, made.text
                    planned = made.json()['data']; pid = planned['production_batch_id']
                    assert planned['status'] == 'CREATED' and planned['items'] == []
                    assert planned['recipe_snapshot']['items'][0]['required_quantity'] == '1.000000'
                    assert (await client.post(production, headers=headers, json=body_prod)).status_code == 409
                    # Snapshot is frozen even if recipe changes before start.
                    await c.execute(text('RESET ROLE'))
                    await c.execute(update(Recipe).where(Recipe.recipe_id == recipe_id).values(quantity='0.5', version=2))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    sources = {'expected_version': 1, 'items': [{'raw_material_batch_id': bid, 'storage_id': str(seed_id('storage')), 'expected_version': 4, 'quantity': '1'}]}
                    start_url = f'{production}/{pid}/start'
                    bad = {**sources, 'items': [{**sources['items'][0], 'quantity': '0.5'}]}
                    assert (await client.post(start_url, headers=headers, json=bad)).status_code == 409
                    bad = {**sources, 'items': [{**sources['items'][0], 'quantity': '3'}]}
                    assert (await client.post(start_url, headers=headers, json=bad)).status_code == 409
                    bad = {**sources, 'items': [{**sources['items'][0], 'storage_id': str(foreign_storage)}]}
                    assert (await client.post(start_url, headers=headers, json=bad)).status_code == 409
                    assert (await client.get(stock + '/stock', headers=headers)).json()['data']['version'] == 4
                    run = await client.post(start_url, headers=headers, json=sources)
                    assert run.status_code == 200, run.text
                    running = run.json()['data']
                    assert running['status'] == 'RUNNING' and running['version'] == 2
                    assert running['items'][0]['batch_version'] == 5
                    assert running['recipe_snapshot'] == planned['recipe_snapshot']
                    assert (await client.post(start_url, headers=headers, json=sources)).status_code == 409
                    assert (await client.post(f'{production}/{pid}/cancel', headers=headers, json={'expected_version': 2})).status_code == 409
                    balance = (await client.get(stock + '/stock', headers=headers)).json()['data']
                    assert balance['available_quantity'] == '1.500000' and balance['issued_quantity'] == '1.000000'
                    assert balance['unallocated_quantity'] == '0.000000'
                    assert (await client.post(stock + '/putaway', headers=headers, json={**allocation, 'expected_version': 5})).status_code == 409
                    issues = (await client.get(stock + '/stock-issues', headers=headers)).json()['data']['items']
                    assert len(issues) == 1 and issues[0]['production_batch_id'] == pid
                    assert (await client.post(f'{production}/{pid}/complete', headers=headers, json={'expected_version': 2, 'actual_quantity': '5'})).status_code == 409
                    complete = await client.post(f'{production}/{pid}/complete', headers=headers, json={'expected_version': 2, 'actual_quantity': '3'})
                    assert complete.status_code == 200, complete.text
                    result = complete.json()['data']
                    assert result['status'] == 'COMPLETED' and result['actual_quantity'] == '3.000000'
                    assert result['version'] == 3 and result['finished_at'] >= result['started_at']
                    assert result['holding_started_at'] is None
                    assert (await client.get(f'{production}/{pid}', headers=headers)).json()['data'] == result
                    assert (await client.get(f'{production}/{foreign}', headers=headers)).status_code == 404
                    assert (await client.get(production, headers=headers, params={'status': 'COMPLETED'})).json()['data']['items'][0]['production_batch_id'] == pid
                    asset_prod = await c.scalar(select(DigitalAsset.asset_uuid).where(DigitalAsset.entity_uuid == UUID(pid)))
                    assert await c.scalar(select(func.count()).select_from(AssetRelationship).where(AssetRelationship.child_uuid == asset_prod, AssetRelationship.relationship_type == 'USED')) == 1
                    events_prod = (await c.execute(select(EventLog.event_type).where(EventLog.entity_uuid == UUID(pid)))).scalars().all()
                    assert set(events_prod) == {'production.created', 'production.started', 'production.completed'}
                    await c.execute(text('RESET ROLE'))
                    holding_rule_id = uuid4()
                    await c.execute(insert(HoldingRule).values(holding_rule_id=holding_rule_id, tenant_id=seed_id('tenant'), food_category='PACKAGING_TEST', maximum_minutes=90, warning_minutes=30, discard_minutes=120))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    types = '/api/v1/packaging-types' 
                    type_body = {'code': 'BOX', 'name': 'Example box', 'volume': '750.000'}
                    t = await client.post(types, headers=headers, json=type_body)
                    assert t.status_code == 201, t.text
                    type_id = t.json()['data']['package_type_id']
                    assert t.json()['data']['volume'] == '750.000'
                    assert (await client.post(types, headers=headers, json=type_body)).status_code == 409
                    assert (await client.post(types, headers=headers, json={**type_body, 'volume': 'NaN'})).status_code == 400
                    assert (await client.get(f'{types}/{foreign}', headers=headers)).status_code == 404
                    changed = await client.put(f'{types}/{type_id}', headers=headers, json={**type_body, 'name': 'New box', 'expected_version': 1})
                    assert changed.status_code == 200, changed.text
                    unused = (await client.post(types, headers=headers, json={**type_body, 'code': 'UNUSED'})).json()['data']
                    unused_id = unused['package_type_id']
                    assert (await client.delete(f'{types}/{unused_id}', headers=headers, params={'expected_version': 1})).status_code == 200
                    assert (await client.get(f'{types}/{unused_id}', headers=headers)).status_code == 404
                    assert (await client.post(types, headers=headers, json={**type_body, 'code': 'UNUSED'})).status_code == 409
                    packages = '/api/v1/packages' 
                    package_body = {'production_batch_id': pid, 'expected_version': 3, 'package_type_id': type_id, 'package_code': 'PKG-001', 'package_number': 1, 'quantity': '2'}
                    assert (await client.post(packages, headers=headers, json={**package_body, 'quantity': '4'})).status_code == 409
                    assert (await client.post(packages, headers=headers, json={**package_body, 'package_type_id': str(foreign)})).status_code == 409
                    pkg = await client.post(packages, headers=headers, json=package_body)
                    assert pkg.status_code == 201, pkg.text
                    package = pkg.json()['data']; pkid = package['package_id']
                    assert package['quantity'] == '2.000000' and package['uom'] == 'portion'
                    assert package['status'] == 'CREATED' and package['timer_status'] == 'SAFE'
                    assert package['holding_policy']['maximum_minutes'] == 60
                    assert package['holding_policy']['rule_id'] == str(holding_rule_id)
                    assert package['holding_policy']['warning_minutes'] == 30
                    assert package['holding_eligible'] is False
                    assert (await client.post(packages, headers=headers, json=package_body)).status_code == 409
                    alloc = (await client.get(f'{production}/{pid}/packaging', headers=headers)).json()['data']
                    assert alloc['version'] == 4 and alloc['unallocated_quantity'] == '1.000000'
                    # Duplicate package after production version update rolls the update back too.
                    assert (await client.post(packages, headers=headers, json={**package_body, 'quantity': '1', 'expected_version': 4})).status_code == 409
                    assert (await client.get(f'{production}/{pid}/packaging', headers=headers)).json()['data']['version'] == 4
                    assert (await client.delete(f'{types}/{type_id}', headers=headers, params={'expected_version': 2})).status_code == 409
                    scanned = await client.get(packages + '/resolve', headers=headers, params={'qr_payload': package['qr_payload']})
                    assert scanned.status_code == 200 and scanned.json()['data']['package_id'] == pkid
                    assert (await client.get(packages + '/resolve', headers=headers, params={'qr_payload': f'fsos:package:{foreign}'})).status_code == 404
                    assert (await client.get(packages + '/resolve', headers=headers, params={'qr_payload': 'invalid'})).status_code == 409
                    assert (await client.get(packages, headers=headers, params={'production_batch_id': pid})).json()['data']['items'][0]['package_id'] == pkid
                    start_h = await client.post(f'{packages}/{pkid}/holding/start', headers=headers, json={'expected_version': 1})
                    assert start_h.status_code == 200, start_h.text
                    active = start_h.json()['data']
                    assert active['holding_started_at'] == result['finished_at'] and active['expired_at'] == package['expired_at']
                    assert active['status'] == 'PACKAGED' and active['version'] == 2
                    assert (await client.post(f'{packages}/{pkid}/holding/start', headers=headers, json={'expected_version': 2})).status_code == 409
                    released = await client.post(f'{packages}/{pkid}/holding/finish', headers=headers, json={'expected_version': 2, 'outcome': 'RELEASED'})
                    assert released.status_code == 200 and released.json()['data']['holding_eligible'] is True
                    # Frozen policy remains shared by subsequent packages even if source changes.
                    await c.execute(text('RESET ROLE'))
                    await c.execute(update(HoldingRule).where(HoldingRule.holding_rule_id == holding_rule_id).values(maximum_minutes=120, discard_minutes=120, warning_minutes=20, version=2))
                    await c.execute(update(FoodItem).where(FoodItem.food_item_id == menu).values(holding_limit_minutes=120))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    next_pkg = await client.post(packages, headers=headers, json={**package_body, 'expected_version': 4, 'package_code': 'PKG-002', 'package_number': 2, 'quantity': '1'})
                    assert next_pkg.status_code == 201, next_pkg.text
                    next_data = next_pkg.json()['data']; next_id = next_data['package_id']
                    assert next_data['expired_at'] == package['expired_at']
                    assert next_data['holding_policy'] == package['holding_policy']
                    discard = await client.post(f'{packages}/{next_id}/holding/finish', headers=headers, json={'expected_version': 1, 'outcome': 'DISCARDED'})
                    assert discard.status_code == 200 and discard.json()['data']['status'] == 'DISCARDED'
                    assert (await client.get(f'{production}/{pid}/packaging', headers=headers)).json()['data']['unallocated_quantity'] == '0.000000'
                    assert (await client.post(packages, headers=headers, json={**package_body, 'expected_version': 5, 'package_code': 'PKG-003', 'package_number': 3, 'quantity': '1'})).status_code == 409
                    from datetime import datetime, timedelta
                    from unittest.mock import patch
                    class Later(datetime):
                        @classmethod
                        def now(cls, tz=None):
                            return datetime.fromisoformat(package['expired_at']) + timedelta(seconds=1)
                    with patch('app.modules.packaging.application.service.datetime', Later):
                        live = (await client.get(f'{packages}/{pkid}', headers=headers)).json()['data']
                        assert live['status'] == 'RELEASED' and live['effective_status'] == 'EXPIRED'
                        assert live['holding_eligible'] is False and live['remaining_seconds'] < 0
                        expired = await client.post(f'{packages}/{pkid}/holding/update', headers=headers, json={'expected_version': 3})
                        assert expired.status_code == 200, expired.text
                        assert expired.json()['data']['status'] == 'EXPIRED'
                        assert (await client.post(f'{packages}/{pkid}/holding/update', headers=headers, json={'expected_version': 4})).status_code == 200
                    assert await c.scalar(select(func.count()).select_from(EventLog).where(EventLog.entity_uuid == UUID(pkid), EventLog.event_type == 'holding.expired')) == 1
                    await c.execute(text('RESET ROLE'))
                    await c.execute(update(RolePermission).where(RolePermission.permission_id.in_(select(Permission.permission_id).where(Permission.permission_code == 'Holding.Update'))).values(deleted_at=func.now()))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    assert (await client.post(f'{packages}/{pkid}/holding/update', headers=headers, json={'expected_version': 5})).status_code == 403
                    assert (await client.get(f'{packages}/{pkid}', headers=headers)).status_code == 200
            finally:
                await outer.rollback()
    finally:
        await engine.dispose()




def test_packaging_openapi():
    schema = create_app().openapi()
    paths = {p: ops for p, ops in schema['paths'].items() if p.startswith(('/api/v1/packages', '/api/v1/packaging-types')) or p.endswith('/packaging')}
    assert sum(len(ops) for ops in paths.values()) == 13
    for ops in paths.values():
        for operation in ops.values():
            assert '422' not in operation['responses']
            assert '400' in operation['responses']
            assert operation['security']


@pytest.mark.parametrize('elapsed,expected', [(0,'SAFE'),(1800,'WARNING'),(3600,'EXPIRED'),(7200,'DISCARD_RECOMMENDED')])
def test_holding_timer_boundaries(elapsed, expected):
    from datetime import UTC, datetime, timedelta

    from app.modules.packaging.application.service import timer
    start = datetime(2026, 1, 1, tzinfo=UTC)
    production = {'finished_at': start, 'holding_policy': {'maximum_minutes':60,'warning_minutes':30,'discard_minutes':120}}
    package = {'expired_at':start+timedelta(minutes=60), 'status':'RELEASED'}
    result = timer(production, package, start+timedelta(seconds=elapsed))
    assert result['timer_status'] == expected
    assert result['holding_eligible'] == (elapsed < 3600)
