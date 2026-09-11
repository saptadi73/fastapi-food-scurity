import os
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, insert, select, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.database.scope import (
    ActorScope,
    InvalidActorError,
    RecordNotFoundError,
    VersionConflictError,
)
from app.modules.authentication.infrastructure.authorization import PermissionDeniedError
from app.modules.authentication.infrastructure.orm import (
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)
from app.modules.master.application.rule_service import RuleService, RuleStateError
from app.modules.master.domain.rule_dsl import RuleDSLValidationError
from app.modules.master.infrastructure.orm import AlarmRule, Tenant

TEST_URL = os.environ.get('FSOS_TEST_DATABASE_URL', '')
ALARM = {'rule_code': 'TEMP', 'rule_name': 'Temperature', 'rule_category': 'TEMPERATURE', 'priority': 'HIGH',
         'condition': {'field': 'temperature', 'op': 'gt', 'value': 5},
         'action': {'dsl_version': 1, 'steps': [{'type': 'alarm', 'code': 'TEMP', 'severity': 'HIGH'}]}}
HOLDING = {'food_category': 'FOOD', 'maximum_minutes': 120, 'warning_minutes': 30, 'discard_minutes': 120}


@pytest.mark.skipif(not TEST_URL, reason='Migrated FSOS_TEST_DATABASE_URL required')
async def test_rule_service_authorization_and_lifecycle():
    assert (make_url(TEST_URL).database or '').startswith('fsos_test')
    engine = create_async_engine(TEST_URL)
    try:
        async with engine.connect() as c:
            transaction = await c.begin()
            try:
                async with AsyncSession(bind=c) as session:
                    tenant, other_tenant, actor, other_actor, role = (uuid4() for _ in range(5))
                    for t, u in ((tenant, actor), (other_tenant, other_actor)):
                        await session.execute(insert(Tenant.__table__).values(tenant_id=t, tenant_code=str(t), tenant_name='Test'))
                        await session.execute(insert(User.__table__).values(user_id=u, tenant_id=t, username='test',
                                              fullname='Test', email='test@example.invalid', status='ACTIVE'))
                    alarm = RuleService(session, ActorScope(tenant, actor), 'alarm')
                    holding = RuleService(session, ActorScope(tenant, actor), 'holding')
                    with pytest.raises(PermissionDeniedError):
                        await alarm.create(ALARM)
                    await session.execute(insert(Role.__table__).values(role_id=role, tenant_id=tenant, role_code='RULES', role_name='Rules'))
                    await session.execute(insert(UserRole.__table__).values(user_role_id=uuid4(), tenant_id=tenant, user_id=actor, role_id=role))
                    grants = {}

                    async def grant(code):
                        identifier = uuid4()
                        grants[code] = identifier
                        await session.execute(insert(Permission.__table__).values(permission_id=identifier, tenant_id=tenant, permission_code=code))
                        await session.execute(insert(RolePermission.__table__).values(role_permission_id=uuid4(), tenant_id=tenant,
                                                                                     role_id=role, permission_id=identifier))

                    await grant('AlarmRule.Write')
                    row = await alarm.create(ALARM)
                    identifier = row['alarm_rule_id']
                    assert row['enabled'] is False and row['version'] == 1 and row['created_by'] == actor
                    with pytest.raises(PermissionDeniedError):
                        await alarm.get(identifier)
                    with pytest.raises(PermissionDeniedError):
                        await alarm.set_enabled(identifier, True, expected_version=1)
                    for code in ('AlarmRule.Read', 'AlarmRule.Activate', 'HoldingRule.Read', 'HoldingRule.Write'):
                        await grant(code)
                    for extra in ({'tenant_id': other_tenant}, {'enabled': True}, {'version': 10}, {'created_by': other_actor}):
                        with pytest.raises(ValidationError):
                            await alarm.create({**ALARM, **extra})
                    with pytest.raises(ValidationError):
                        await alarm.save(identifier, {**ALARM, 'condition': {}}, expected_version=1)
                    assert len(await alarm.history(identifier)) == 1
                    enabled = await alarm.set_enabled(identifier, True, expected_version=1)
                    assert enabled['enabled'] and enabled['version'] == 2 and enabled['updated_by'] == actor
                    with pytest.raises(RuleStateError):
                        await alarm.save(identifier, ALARM, expected_version=2)
                    with pytest.raises(VersionConflictError):
                        await alarm.set_enabled(identifier, False, expected_version=1)
                    assert (await alarm.set_enabled(identifier, True, expected_version=2))['version'] == 2
                    await alarm.set_enabled(identifier, False, expected_version=2)
                    changed = await alarm.save(identifier, {**ALARM, 'rule_name': 'Edited'}, expected_version=3)
                    assert changed['version'] == 4
                    history = await alarm.history(identifier)
                    assert [r['version'] for r in history] == [4, 3, 2, 1]
                    assert history[-1]['snapshot']['rule_name'] == 'Temperature'
                    assert len(await alarm.history(identifier, offset=1, limit=1)) == 1
                    with pytest.raises(ValueError):
                        await alarm.save(identifier, ALARM, expected_version=True)
                    with pytest.raises(ValueError):
                        await alarm.history(identifier, limit=101)
                    for model in (User, Tenant):
                        async with session.begin_nested() as savepoint:
                            await session.execute(update(model.__table__).where(model.tenant_id == tenant).values(status='INACTIVE'))
                            with pytest.raises(InvalidActorError):
                                await alarm.set_enabled(identifier, True, expected_version=4)
                            await savepoint.rollback()
                    # Soft deletion at any edge of the RBAC chain must revoke access.
                    for model in (UserRole, Role, RolePermission, Permission):
                        async with session.begin_nested() as savepoint:
                            await session.execute(update(model.__table__).where(model.tenant_id == tenant).values(deleted_at=func.now()))
                            with pytest.raises(PermissionDeniedError):
                                await alarm.get(identifier)
                            await savepoint.rollback()
                    with pytest.raises(InvalidActorError):
                        await RuleService(session, ActorScope(tenant, other_actor), 'alarm').get(identifier)
                    # Authorized actor must still not see a foreign tenant's rule or history.
                    foreign = uuid4()
                    await session.execute(insert(AlarmRule.__table__).values(**ALARM, alarm_rule_id=foreign, tenant_id=other_tenant))
                    for operation in (alarm.get(foreign), alarm.history(foreign),
                                      alarm.save(foreign, ALARM, expected_version=1),
                                      alarm.set_enabled(foreign, True, expected_version=1)):
                        with pytest.raises(RecordNotFoundError):
                            await operation
                    # Legacy invalid DSL may be disabled but cannot be enabled.
                    await session.execute(update(AlarmRule.__table__).where(AlarmRule.alarm_rule_id == identifier).values(condition={'legacy': True}))
                    with pytest.raises(RuleDSLValidationError):
                        await alarm.set_enabled(identifier, True, expected_version=5)
                    assert (await alarm.set_enabled(identifier, False, expected_version=5))['version'] == 5
                    for bad in ({**HOLDING, 'warning_minutes': 121}, {**HOLDING, 'maximum_minutes': True}):
                        with pytest.raises(ValidationError):
                            await holding.create(bad)
                    h = await holding.create(HOLDING)
                    saved = await holding.save(h['holding_rule_id'], {**HOLDING, 'maximum_minutes': 110}, expected_version=1)
                    assert saved['version'] == 2 and len(await holding.history(h['holding_rule_id'])) == 2
                    with pytest.raises(ValueError):
                        await holding.set_enabled(h['holding_rule_id'], True, expected_version=2)
            finally:
                await transaction.rollback()
            assert await c.scalar(select(Tenant.tenant_id).where(Tenant.tenant_id == tenant)) is None
    finally:
        await engine.dispose()
