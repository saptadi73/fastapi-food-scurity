import os
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.database.development_seed import seed_development, seed_id
from app.core.database.runtime_role import provision_runtime_role
from app.core.database.telemetry_permissions import (
    TELEMETRY_PERMISSIONS,
    TelemetryGrantConflictError,
    provision_telemetry_permissions,
)
from app.modules.authentication.infrastructure.orm import Permission, RolePermission

TEST_URL = os.environ.get('FSOS_TEST_DATABASE_URL', '')


@pytest.mark.skipif(not TEST_URL, reason='Migrated test database required')
async def test_telemetry_permission_provisioning():
    assert (make_url(TEST_URL).database or '').startswith('fsos_test')
    engine = create_async_engine(TEST_URL)
    try:
        async with engine.connect() as c:
            outer = await c.begin()
            try:
                async with AsyncSession(bind=c) as db:
                    await seed_development(db, environment='development')
                    args = {'tenant_id': seed_id('tenant'), 'actor_id': seed_id('actor'), 'role_id': seed_id('role'),
                            'permissions': list(TELEMETRY_PERMISSIONS), 'environment': 'development'}
                    before = await db.scalar(select(func.count()).select_from(Permission))
                    preview = await provision_telemetry_permissions(db, **args)
                    assert preview['missing_permissions'] == 4 and preview['created_grants'] == 0
                    assert await db.scalar(select(func.count()).select_from(Permission)) == before
                    for invalid in ({'environment': 'production'}, {'permissions': ['Admin.All']}, {'permissions': []}, {'permissions': ['Alarm.Read', 'Alarm.Read']}):
                        with pytest.raises(ValueError):
                            await provision_telemetry_permissions(db, **{**args, **invalid}, apply=True)
                    for invalid in ({'tenant_id': uuid4()}, {'actor_id': uuid4()}, {'role_id': uuid4()}):
                        with pytest.raises(TelemetryGrantConflictError):
                            await provision_telemetry_permissions(db, **{**args, **invalid}, apply=True)
                    async with db.begin_nested() as nested:
                        applied = await provision_telemetry_permissions(db, **args, apply=True)
                        assert applied['created_permissions'] == 4 and applied['created_grants'] == 4
                        assert (await provision_telemetry_permissions(db, **args, apply=True))['created_grants'] == 0
                        pid = await db.scalar(select(Permission.permission_id).where(Permission.tenant_id == seed_id('tenant'), Permission.permission_code == 'Alarm.Read'))
                        assert await db.scalar(select(Permission.created_by).where(Permission.permission_id == pid)) == seed_id('actor')
                        for model in (Permission, RolePermission):
                            async with db.begin_nested() as revoked:
                                await db.execute(update(model.__table__).where(model.permission_id == pid).values(deleted_at=func.now()))
                                with pytest.raises(TelemetryGrantConflictError):
                                    await provision_telemetry_permissions(db, **args, apply=True)
                                await revoked.rollback()
                        await nested.rollback()
                    assert await db.scalar(select(func.count()).select_from(Permission)) == before
                await provision_runtime_role(c)
                async with c.begin_nested() as restricted:
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    async with AsyncSession(bind=c) as db:
                        with pytest.raises(DBAPIError):
                            await provision_telemetry_permissions(db, **args, apply=True)
                    await restricted.rollback()
            finally:
                await outer.rollback()
    finally:
        await engine.dispose()
