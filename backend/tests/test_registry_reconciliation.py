import os
from uuid import uuid4

import pytest
from sqlalchemy import func, insert, select, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.database.development_seed import seed_development, seed_id
from app.core.database.scope import ActorScope, InvalidActorError
from app.modules.authentication.infrastructure.authorization import PermissionDeniedError
from app.modules.authentication.infrastructure.orm import RolePermission, User
from app.modules.master.infrastructure.orm import Kitchen, Tenant
from app.modules.traceability.application.registry_service import RegistryService
from app.modules.traceability.infrastructure.orm import DigitalAsset

TEST_URL = os.environ.get('FSOS_TEST_DATABASE_URL', '')


@pytest.mark.skipif(not TEST_URL, reason='Migrated FSOS_TEST_DATABASE_URL required')
async def test_registry_reconciliation_scope_drift_pagination_and_preservation():
    assert (make_url(TEST_URL).database or '').startswith('fsos_test')
    engine = create_async_engine(TEST_URL)
    try:
        async with engine.connect() as c:
            transaction = await c.begin()
            try:
                async with AsyncSession(bind=c) as session:
                    await seed_development(session, environment='development')
                    tenant, actor = seed_id('tenant'), seed_id('actor')
                    service = RegistryService(session, ActorScope(tenant, actor))
                    synced = await service.sync('KITCHEN', seed_id('kitchen'))
                    clean = await service.reconcile('KITCHEN')
                    assert clean['issue_count'] == 0 and clean['processed'] == 1
                    # Soft deletion is a source projection, not a physically missing source.
                    await session.execute(update(Kitchen.__table__).where(Kitchen.kitchen_id == seed_id('kitchen')).values(
                        kitchen_name='Renamed', deleted_at=func.now(), deleted_by=actor,
                    ))
                    drift = (await service.reconcile('KITCHEN'))['items'][0]
                    assert drift['state'] == 'PROJECTION_MISMATCH' and drift['source_deleted'] is True
                    assert set(drift['changed_fields']) == {'name', 'deleted_at', 'deleted_by'}
                    assert drift['version'] == synced['version']
                    await service.sync('KITCHEN', seed_id('kitchen'))
                    assert (await service.reconcile('KITCHEN'))['issue_count'] == 0

                    foreign_tenant, foreign_kitchen = uuid4(), uuid4()
                    await session.execute(insert(Tenant.__table__).values(
                        tenant_id=foreign_tenant, tenant_code='RECON_OTHER', tenant_name='Other',
                    ))
                    await session.execute(insert(Kitchen.__table__).values(
                        tenant_id=foreign_tenant, kitchen_id=foreign_kitchen,
                        kitchen_code='OTHER', kitchen_name='Private name',
                    ))
                    # Tenant mismatch and wrong source type both appear missing; no foreign data leaks.
                    for entity in (uuid4(), foreign_kitchen, seed_id('supplier')):
                        await session.execute(insert(DigitalAsset.__table__).values(
                            asset_uuid=uuid4(), tenant_id=tenant, asset_type='KITCHEN',
                            entity_uuid=entity, code=str(entity), name='Preserved evidence',
                        ))
                    await session.execute(insert(DigitalAsset.__table__).values(
                        asset_uuid=uuid4(), tenant_id=foreign_tenant, asset_type='KITCHEN',
                        entity_uuid=foreign_kitchen, code='FOREIGN', name='Private name',
                    ))
                    before = (await session.execute(select(DigitalAsset.__table__).order_by(DigitalAsset.asset_uuid))).mappings().all()
                    cursor, items = None, []
                    while True:
                        page = await service.reconcile('KITCHEN', after_id=cursor, limit=1)
                        items.extend(page['items'])
                        assert page['processed'] == 1
                        cursor = page['next_cursor']
                        if cursor is None:
                            break
                    assert len(items) == 4 and len({item['asset_uuid'] for item in items}) == 4
                    missing = [item for item in items if item['state'] == 'SOURCE_MISSING']
                    assert len(missing) == 3
                    assert all(item['source_deleted'] is None and item['changed_fields'] == [] for item in missing)
                    assert 'Private name' not in str(items)
                    empty = await service.reconcile('KITCHEN', after_id=items[-1]['asset_uuid'])
                    assert empty['items'] == [] and empty['last_id'] is None and empty['next_cursor'] is None
                    after = (await session.execute(select(DigitalAsset.__table__).order_by(DigitalAsset.asset_uuid))).mappings().all()
                    assert before == after
                    for limit in (0, 201, True, 1.5):
                        with pytest.raises(ValueError):
                            await service.reconcile('KITCHEN', limit=limit)
                    with pytest.raises(ValueError):
                        await service.reconcile('UNKNOWN')
                    with pytest.raises(ValueError):
                        await service.reconcile('KITCHEN', after_id='bad-cursor')
                    await session.execute(update(RolePermission.__table__).where(RolePermission.tenant_id == tenant).values(deleted_at=func.now()))
                    with pytest.raises(PermissionDeniedError):
                        await service.reconcile('KITCHEN')
                    await session.execute(update(User.__table__).where(User.user_id == actor).values(status='INACTIVE'))
                    with pytest.raises(InvalidActorError):
                        await service.reconcile('KITCHEN')
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()
