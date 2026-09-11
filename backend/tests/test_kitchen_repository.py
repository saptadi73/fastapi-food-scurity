import os
from uuid import uuid4

import pytest
from sqlalchemy import insert, select, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.database.scope import (
    ActorScope,
    InvalidActorError,
    RecordNotFoundError,
    VersionConflictError,
)
from app.modules.authentication.infrastructure.orm import User
from app.modules.master.infrastructure.kitchen_repository import KitchenRepository
from app.modules.master.infrastructure.orm import Kitchen, Tenant
from app.modules.traceability.infrastructure.orm import DigitalAsset

TEST_URL = os.environ.get("FSOS_TEST_DATABASE_URL", "")


@pytest.mark.skipif(not TEST_URL, reason="FSOS_TEST_DATABASE_URL required; migrate test database first")
async def test_scoped_repository():
    assert (make_url(TEST_URL).database or '').startswith('fsos_test')
    engine = create_async_engine(TEST_URL)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                async with AsyncSession(bind=connection, expire_on_commit=False) as session:
                    tenant_a, tenant_b, actor_a, actor_b = (uuid4() for _ in range(4))
                    for tenant, actor in ((tenant_a, actor_a), (tenant_b, actor_b)):
                        await session.execute(insert(Tenant.__table__).values(
                            tenant_id=tenant, tenant_code=str(tenant), tenant_name='Repository test',
                        ))
                        await session.execute(insert(User.__table__).values(
                            user_id=actor, tenant_id=tenant, username='editor', fullname='Test',
                            email='editor@example.invalid', status='ACTIVE',
                        ))
                    a = KitchenRepository(session, ActorScope(tenant_a, actor_a))
                    b = KitchenRepository(session, ActorScope(tenant_b, actor_b))
                    row = await a.create({'kitchen_code': 'TEST', 'kitchen_name': 'Initial'})
                    identifier = row['kitchen_id']
                    assert row['created_by'] == row['updated_by'] == actor_a
                    assert row['version'] == 1 and row['tenant_id'] == tenant_a
                    registry = (await session.execute(select(DigitalAsset.__table__).where(DigitalAsset.entity_uuid == identifier))).mappings().one()
                    assert registry['name'] == 'Initial' and registry['tenant_id'] == tenant_a
                    assert [item['kitchen_id'] for item in await a.list(limit=1)] == [identifier]
                    assert await a.list(offset=1) == []
                    assert await b.list() == []
                    for operation in (b.get(identifier), b.update(identifier, {'kitchen_name': 'Attack'}, expected_version=1),
                                      b.soft_delete(identifier, expected_version=1)):
                        with pytest.raises(RecordNotFoundError):
                            await operation
                    for forbidden in ('tenant_id', 'created_by', 'version', 'deleted_at', 'location', 'kitchen_id'):
                        with pytest.raises(ValueError):
                            await a.update(identifier, {forbidden: None}, expected_version=1)
                        with pytest.raises(ValueError):
                            await a.create({forbidden: None})
                    changed = await a.update(identifier, {'kitchen_name': 'Edited'}, expected_version=1)
                    assert changed['version'] == 2
                    assert changed['created_at'] == row['created_at']
                    assert changed['updated_at'] >= row['updated_at']
                    with pytest.raises(VersionConflictError):
                        await a.update(identifier, {'kitchen_name': 'Stale editor'}, expected_version=1)
                    with pytest.raises(VersionConflictError):
                        await a.soft_delete(identifier, expected_version=1)
                    assert (await a.get(identifier))['kitchen_name'] == 'Edited'
                    bad_scope = KitchenRepository(session, ActorScope(tenant_a, actor_b))
                    with pytest.raises(InvalidActorError):
                        await bad_scope.get(identifier)
                    await session.execute(update(User.__table__).where(User.user_id == actor_a).values(status='INACTIVE'))
                    with pytest.raises(InvalidActorError):
                        await a.list()
                    await session.execute(update(User.__table__).where(User.user_id == actor_a).values(status='ACTIVE'))
                    await session.execute(update(Tenant.__table__).where(Tenant.tenant_id == tenant_a).values(status='INACTIVE'))
                    with pytest.raises(InvalidActorError):
                        await a.update(identifier, {'kitchen_name': 'Blocked tenant'}, expected_version=2)
                    await session.execute(update(Tenant.__table__).where(Tenant.tenant_id == tenant_a).values(status='ACTIVE'))
                    removed = await a.soft_delete(identifier, expected_version=2)
                    assert removed['version'] == 3 and removed['deleted_by'] == actor_a
                    assert removed['deleted_at'] is not None
                    registry_after = (await session.execute(select(DigitalAsset.__table__).where(DigitalAsset.entity_uuid == identifier))).mappings().one()
                    assert registry_after['asset_uuid'] == registry['asset_uuid']
                    assert registry_after['name'] == 'Edited' and registry_after['deleted_by'] == actor_a
                    assert registry_after['deleted_at'] is not None
                    assert await a.list() == []
                    with pytest.raises(RecordNotFoundError):
                        await a.get(identifier)
                    with pytest.raises(RecordNotFoundError):
                        await a.update(identifier, {'kitchen_name': 'Revive'}, expected_version=3)
                    assert await session.scalar(select(Kitchen.kitchen_id).where(Kitchen.kitchen_id == identifier)) == identifier
                    for offset, limit in ((-1, 20), (0, 101), (0, True)):
                        with pytest.raises(ValueError):
                            await a.list(offset=offset, limit=limit)
                    # Repository never commits: caller rollback removes its inserts and updates.
            finally:
                await transaction.rollback()
            assert await connection.scalar(select(Tenant.tenant_id).where(Tenant.tenant_id == tenant_a)) is None
    finally:
        await engine.dispose()
