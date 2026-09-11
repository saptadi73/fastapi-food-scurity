import os
from uuid import UUID, uuid4

import httpx
import pytest
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
from app.modules.master.infrastructure.orm import FoodItem, RawMaterial, Recipe, Tenant
from app.modules.production.infrastructure.orm import ProductionBatch
from main import create_app

TEST_URL = os.environ.get('FSOS_TEST_DATABASE_URL', '')
CODEC = AccessTokenCodec(SecretStr('alarm-http-test-only-key-at-least-32-bytes'))


@pytest.mark.skipif(not TEST_URL, reason='Migrated test database required')
async def test_food_business_flow():
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
                    await db.execute(insert(FoodItem).values(food_item_id=foreign, tenant_id=other, food_code='FOREIGN', food_name='Foreign', uom='portion'))
                    foreign_material, foreign_recipe = uuid4(), uuid4()
                    await db.execute(insert(RawMaterial).values(raw_material_id=foreign_material, tenant_id=other, material_code='FOREIGN', material_name='Foreign', uom='kg'))
                    await db.execute(insert(Recipe).values(recipe_id=foreign_recipe, tenant_id=other, food_item_id=foreign, raw_material_id=foreign_material, quantity=1, uom='kg'))
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
                    foods, recipes = '/api/v1/food-items', '/api/v1/recipes'
                    assert (await client.get(foods)).status_code == 401
                    pair = (await client.post('/api/v1/auth/login', json={'tenant_id': str(seed_id('tenant')), 'username': 'dev-maintenance', 'password': 'alarm test passphrase'})).json()['data']
                    headers = {'Authorization': f"Bearer {pair['access_token']}"}
                    food_body = {'food_code': 'TEST_MENU', 'food_name': 'Example menu', 'uom': 'portion', 'holding_limit_minutes': 60}
                    created = await client.post(foods, json=food_body, headers=headers)
                    assert created.status_code == 201, created.text
                    food = created.json()['data']; fid = food['food_item_id']
                    assert food['version'] == 1 and food['created_by'] == str(seed_id('actor'))
                    assert created.headers['Cache-Control'] == 'no-store'
                    assert (await client.get(f'{foods}/{fid}', headers=headers)).json()['data'] == food
                    assert (await client.post(foods, json=food_body, headers=headers)).status_code == 409
                    assert (await client.get(f'{foods}/{foreign}', headers=headers)).status_code == 404
                    for bad in ({**food_body, 'uom': ' '}, {**food_body, 'holding_limit_minutes': True}, {**food_body, 'holding_limit_minutes': -1}, {**food_body, 'tenant_id': str(other)}):
                        assert (await client.post(foods, json=bad, headers=headers)).status_code == 400
                    recipe_body = {'food_item_id': fid, 'raw_material_id': str(seed_id('material')), 'quantity': '0.125000', 'uom': 'kg'}
                    for bad in ({**recipe_body, 'food_item_id': str(foreign)}, {**recipe_body, 'raw_material_id': str(foreign_material)}, {**recipe_body, 'uom': 'g'}):
                        assert (await client.post(recipes, json=bad, headers=headers)).status_code == 409
                    for quantity in ('NaN', 'Infinity', '0', '-1', '0.1234567', True):
                        assert (await client.post(recipes, json={**recipe_body, 'quantity': quantity}, headers=headers)).status_code == 400
                    created = await client.post(recipes, json=recipe_body, headers=headers)
                    assert created.status_code == 201, created.text
                    recipe = created.json()['data']; rid = recipe['recipe_id']
                    assert recipe['quantity'] == '0.125000' and recipe['uom'] == 'kg'
                    assert (await client.get(f'{recipes}/{rid}', headers=headers)).json()['data'] == recipe
                    assert (await client.get(f'{recipes}/{foreign_recipe}', headers=headers)).status_code == 404
                    assert (await client.post(recipes, json=recipe_body, headers=headers)).status_code == 409
                    rows = (await client.get(recipes, params={'food_item_id': fid, 'limit': 1}, headers=headers)).json()['data']
                    assert rows['items'] == [recipe] and rows['next_offset'] is None
                    assert (await client.get(recipes, params={'food_item_id': str(foreign)}, headers=headers)).json()['data']['items'] == []
                    assert (await client.get(foods, params={'limit': 0}, headers=headers)).status_code == 400
                    assert (await client.delete(f'{foods}/{fid}', params={'expected_version': 1}, headers=headers)).status_code == 409
                    assert (await client.delete(f"/api/v1/raw-materials/{seed_id('material')}", params={'expected_version': 1}, headers=headers)).status_code == 409
                    changed = await client.put(f'{recipes}/{rid}', json={**recipe_body, 'quantity': '0.2', 'expected_version': 1}, headers=headers)
                    assert changed.status_code == 200, changed.text
                    assert changed.json()['data']['quantity'] == '0.200000' and changed.json()['data']['version'] == 2
                    assert (await client.put(f'{recipes}/{rid}', json={**recipe_body, 'expected_version': 1}, headers=headers)).status_code == 409
                    second = (await client.post(foods, json={**food_body, 'food_code': 'SECOND'}, headers=headers)).json()['data']
                    assert (await client.put(f'{recipes}/{rid}', json={**recipe_body, 'food_item_id': second['food_item_id'], 'expected_version': 2}, headers=headers)).status_code == 409
                    assert (await client.put(f'{foods}/{fid}', json={**food_body, 'uom': 'kg', 'expected_version': 1}, headers=headers)).status_code == 409
                    inactive = await client.put(f'{foods}/{fid}', json={**food_body, 'status': 'INACTIVE', 'expected_version': 1}, headers=headers)
                    assert inactive.status_code == 200, inactive.text
                    assert (await client.put(f'{recipes}/{rid}', json={**recipe_body, 'expected_version': 2}, headers=headers)).status_code == 409
                    filtered = (await client.get(foods, params={'status': 'INACTIVE'}, headers=headers)).json()['data']
                    assert [i['food_item_id'] for i in filtered['items']] == [fid]
                    assert (await client.delete(f'{foods}/{fid}', params={'expected_version': 2}, headers=headers)).status_code == 409
                    assert (await client.delete(f'{recipes}/{rid}', params={'expected_version': 1}, headers=headers)).status_code == 409
                    removed = await client.delete(f'{recipes}/{rid}', params={'expected_version': 2}, headers=headers)
                    assert removed.status_code == 200 and removed.json()['data']['deleted_at']
                    assert (await client.get(f'{recipes}/{rid}', headers=headers)).status_code == 404
                    assert (await client.delete(f'{recipes}/{rid}', params={'expected_version': 3}, headers=headers)).status_code == 404
                    reactivated = await client.put(f'{foods}/{fid}', json={**food_body, 'expected_version': 2}, headers=headers)
                    assert reactivated.status_code == 200
                    assert (await client.post(recipes, json=recipe_body, headers=headers)).status_code == 409
                    removed = await client.delete(f'{foods}/{fid}', params={'expected_version': 3}, headers=headers)
                    assert removed.status_code == 200 and removed.json()['data']['version'] == 4
                    assert (await client.get(f'{foods}/{fid}', headers=headers)).status_code == 404
                    assert (await client.post(foods, json=food_body, headers=headers)).status_code == 409
                    # Historical production reference blocks menu deletion even without recipes.
                    await c.execute(text('RESET ROLE'))
                    await c.execute(insert(ProductionBatch).values(production_batch_id=uuid4(), tenant_id=seed_id('tenant'), batch_code='FOOD-HISTORY', kitchen=seed_id('kitchen'), menu=UUID(second['food_item_id'])))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    assert (await client.delete(f"{foods}/{second['food_item_id']}", params={'expected_version': 1}, headers=headers)).status_code == 409
                    # Revocations are observed with the original access token, and Delete is independent.
                    third = (await client.post(foods, json={**food_body, 'food_code': 'THIRD'}, headers=headers)).json()['data']
                    await c.execute(text('RESET ROLE'))
                    await c.execute(update(RolePermission).where(RolePermission.permission_id.in_(select(Permission.permission_id).where(Permission.permission_code.in_(['FoodItem.Read', 'FoodItem.Write', 'Recipe.Write'])))).values(deleted_at=func.now()))
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    assert (await client.get(foods, headers=headers)).status_code == 403
                    assert (await client.post(foods, json=food_body, headers=headers)).status_code == 403
                    assert (await client.post(recipes, json=recipe_body, headers=headers)).status_code == 403
                    assert (await client.get(recipes, headers=headers)).status_code == 200
                    assert (await client.delete(f"{foods}/{third['food_item_id']}", params={'expected_version': 1}, headers=headers)).status_code == 200
            finally:
                await outer.rollback()
    finally:
        await engine.dispose()



def test_food_openapi():
    schema = create_app().openapi()
    paths = {p: ops for p, ops in schema['paths'].items() if p.startswith(('/api/v1/food-items', '/api/v1/recipes'))}
    assert sum(len(ops) for ops in paths.values()) == 10
    for ops in paths.values():
        for operation in ops.values():
            assert '422' not in operation['responses']
            assert '400' in operation['responses']
            assert operation['security']
