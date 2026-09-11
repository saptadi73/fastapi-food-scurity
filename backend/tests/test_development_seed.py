import os
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.database.development_seed import SeedConflictError, seed_development, seed_id
from app.modules.authentication.infrastructure.orm import RolePermission, User
from app.modules.master.infrastructure.orm import Kitchen, Tenant
from app.modules.traceability.infrastructure.orm import DigitalAsset

TEST_URL = os.environ.get('FSOS_TEST_DATABASE_URL', '')


async def test_seed_rejects_production_before_query():
    session = AsyncMock()
    with pytest.raises(ValueError):
        await seed_development(session, environment='production')
    session.execute.assert_not_awaited()


@pytest.mark.skipif(not TEST_URL, reason='Migrated FSOS_TEST_DATABASE_URL required')
async def test_seed_is_repeatable_and_preserves_existing_data():
    assert (make_url(TEST_URL).database or '').startswith('fsos_test')
    engine = create_async_engine(TEST_URL)
    try:
        async with engine.connect() as c:
            transaction = await c.begin()
            try:
                async with AsyncSession(bind=c) as session:
                    first = await seed_development(session, environment='development')
                    assert first['created'] == 23
                    assert sum(first['registry_processed'].values()) == 6
                    assets = (await session.execute(select(DigitalAsset.asset_uuid, DigitalAsset.version).order_by(DigitalAsset.asset_uuid))).all()
                    second = await seed_development(session, environment='development')
                    assert second['created'] == 0 and second['actor_id'] == first['actor_id']
                    assert (await session.execute(select(DigitalAsset.asset_uuid, DigitalAsset.version).order_by(DigitalAsset.asset_uuid))).all() == assets
                    assert await session.scalar(select(User.password_hash).where(User.user_id == seed_id('actor'))) is None
                    await session.execute(update(Kitchen.__table__).where(Kitchen.kitchen_id == seed_id('kitchen')).values(kitchen_name='Nama disesuaikan'))
                    await seed_development(session, environment='development')
                    assert await session.scalar(select(Kitchen.kitchen_name).where(Kitchen.kitchen_id == seed_id('kitchen'))) == 'Nama disesuaikan'
                    for hard_delete in (False, True):
                        async with session.begin_nested() as savepoint:
                            grant = RolePermission.__table__
                            statement = delete(grant) if hard_delete else update(grant).values(deleted_at=func.now())
                            await session.execute(statement.where(grant.c.role_permission_id == seed_id('grant:AssetRegistry.Sync')))
                            with pytest.raises(SeedConflictError):
                                await seed_development(session, environment='development')
                            await savepoint.rollback()
                    async with session.begin_nested() as savepoint:
                        await session.execute(update(User.__table__).where(User.user_id == seed_id('actor')).values(status='INACTIVE'))
                        with pytest.raises(SeedConflictError):
                            await seed_development(session, environment='development')
                        await savepoint.rollback()
                    # Even after successful seed/backfill, outer rollback removes every fixture.
            finally:
                await transaction.rollback()
            assert await c.scalar(select(Tenant.tenant_id).where(Tenant.tenant_id == seed_id('tenant'))) is None
    finally:
        await engine.dispose()
