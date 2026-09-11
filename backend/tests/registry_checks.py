from uuid import uuid4

import pytest
from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.scope import ActorScope, RecordNotFoundError
from app.modules.authentication.infrastructure.authorization import PermissionDeniedError
from app.modules.authentication.infrastructure.orm import (
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)
from app.modules.master.infrastructure.orm import Kitchen
from app.modules.traceability.application.registry_service import RegistryService
from app.modules.traceability.infrastructure.orm import DigitalAsset
from app.modules.traceability.infrastructure.registry import SOURCES


async def verify_registry(c, tenant, other_tenant):
    # Preserve the original fixture counts for subsequent migration downgrade checks.
    savepoint = await c.begin_nested()
    try:
        async with AsyncSession(bind=c) as session:
            actor = await session.scalar(select(User.user_id).where(User.tenant_id == tenant))
            await session.execute(update(User.__table__).where(User.user_id == actor).values(status='ACTIVE'))
            service = RegistryService(session, ActorScope(tenant, actor))
            with pytest.raises(PermissionDeniedError):
                await service.backfill('KITCHEN')
            role, permission = uuid4(), uuid4()
            await session.execute(insert(Role.__table__).values(role_id=role, tenant_id=tenant, role_code='REGISTRY', role_name='Registry'))
            await session.execute(insert(Permission.__table__).values(permission_id=permission, tenant_id=tenant, permission_code='AssetRegistry.Sync'))
            await session.execute(insert(UserRole.__table__).values(user_role_id=uuid4(), tenant_id=tenant, user_id=actor, role_id=role))
            await session.execute(insert(RolePermission.__table__).values(role_permission_id=uuid4(), tenant_id=tenant, role_id=role, permission_id=permission))
            for kind, adapter in SOURCES.items():
                table = adapter.model.__table__
                ids = (await session.execute(select(table.c[adapter.key]).where(table.c.tenant_id == tenant))).scalars().all()
                assert ids, kind
                for identifier in ids:
                    first = await service.sync(kind, identifier)
                    assert first['tenant_id'] == tenant and first['entity_uuid'] == identifier and first['asset_type'] == kind
                    assert await service.sync(kind, identifier) == first
                cursor, seen = None, []
                while True:
                    batch = await service.backfill(kind, after_id=cursor, limit=1)
                    if batch['processed'] == 0:
                        break
                    cursor = batch['last_id']
                    seen.append(cursor)
                assert set(seen) == set(ids) and len(seen) == len(ids)
                report = await service.reconcile(kind)
                by_source = {item['entity_uuid']: item for item in report['items']}
                assert all(by_source[identifier]['state'] == 'IN_SYNC' for identifier in ids), kind
            foreign = await session.scalar(select(Kitchen.kitchen_id).where(Kitchen.tenant_id == other_tenant))
            with pytest.raises(RecordNotFoundError):
                await service.sync('KITCHEN', foreign)
            with pytest.raises(ValueError):
                await service.sync('UNKNOWN', uuid4())
            identifier = await session.scalar(select(Kitchen.kitchen_id).where(Kitchen.tenant_id == tenant))
            with pytest.raises(RecordNotFoundError):
                await service.sync('PACKAGE', identifier)
            before = await service.sync('KITCHEN', identifier)
            await session.execute(update(Kitchen.__table__).where(Kitchen.kitchen_id == identifier).values(kitchen_name='Changed'))
            changed = await service.sync('KITCHEN', identifier)
            assert changed['asset_uuid'] == before['asset_uuid'] and changed['name'] == 'Changed'
            assert changed['version'] == before['version'] + 1
            await session.execute(update(Kitchen.__table__).where(Kitchen.kitchen_id == identifier).values(deleted_at=func.now(), deleted_by=actor))
            deleted = await service.sync('KITCHEN', identifier)
            assert deleted['deleted_at'] is not None and deleted['deleted_by'] == actor
            assert deleted['asset_uuid'] == before['asset_uuid']
    finally:
        await savepoint.rollback()
    assert await c.scalar(select(func.count()).select_from(DigitalAsset.__table__)) == 3
