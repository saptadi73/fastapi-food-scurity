import os

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.database.development_seed import seed_development, seed_id
from app.core.database.runtime_login import provision_runtime_login
from app.core.database.runtime_role import provision_runtime_role
from app.core.database.scope import ActorScope
from app.modules.master.application.rule_service import RuleService
from app.modules.master.infrastructure.kitchen_repository import KitchenRepository
from app.modules.traceability.application.registry_service import RegistryService

TEST_URL = os.environ.get('FSOS_TEST_DATABASE_URL', '')


@pytest.mark.skipif(not TEST_URL, reason='Migrated FSOS_TEST_DATABASE_URL required')
async def test_runtime_role_services_and_denied_operations():
    assert (make_url(TEST_URL).database or '').startswith('fsos_test')
    engine = create_async_engine(TEST_URL)
    try:
        async with engine.connect() as c:
            transaction = await c.begin()
            try:
                async with AsyncSession(bind=c) as session:
                    await seed_development(session, environment='development')
                    await provision_runtime_role(c)
                    await provision_runtime_role(c)
                    assert await provision_runtime_login(c, 'test-only-generated-secret-that-is-not-a-default-password') is True
                    assert await provision_runtime_login(c, 'not-rotated', allow_existing=True) is False
                    with pytest.raises(ValueError):
                        await provision_runtime_login(c, 'unrequested-password-reset')
                    assert await session.scalar(text("SELECT pg_has_role('fsos_app','fsos_runtime','MEMBER')")) is True
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    scope = ActorScope(seed_id('tenant'), seed_id('actor'))
                    repo = KitchenRepository(session, scope)
                    kitchen = await repo.get(seed_id('kitchen'))
                    changed = await repo.update(seed_id('kitchen'), {'kitchen_name': 'Runtime edit'}, expected_version=kitchen['version'])
                    assert changed['kitchen_name'] == 'Runtime edit'
                    assert (await RegistryService(session, scope).backfill('KITCHEN'))['processed'] == 1
                    report = await RegistryService(session, scope).reconcile('KITCHEN')
                    assert report['processed'] == 1 and report['issue_count'] == 0
                    service = RuleService(session, scope, 'alarm')
                    rule = await service.create({
                        'rule_code': 'RUNTIME_TEST', 'rule_name': 'Runtime', 'rule_category': 'TEMPERATURE', 'priority': 'HIGH',
                        'condition': {'field': 'temperature', 'op': 'gt', 'value': 5},
                        'action': {'dsl_version': 1, 'steps': [{'type': 'alarm', 'code': 'TEST', 'severity': 'HIGH'}]},
                    })
                    enabled = await service.set_enabled(rule['alarm_rule_id'], True, expected_version=1)
                    assert enabled['version'] == 2 and len(await service.history(rule['alarm_rule_id'])) == 2
                    for sql in (
                        'CREATE TABLE public.runtime_forbidden (id integer)',
                        'CREATE TEMP TABLE runtime_forbidden (id integer)',
                        'ALTER TABLE public.alarm_log DISABLE TRIGGER ALL',
                        'TRUNCATE public.kitchen CASCADE',
                        'DELETE FROM public.digital_asset',
                        "UPDATE public.app_user SET status='ACTIVE'",
                        'DELETE FROM public.role_permission',
                        'INSERT INTO public.alarm_rule_revision SELECT * FROM public.alarm_rule_revision',
                        "SELECT public.fsos_create_telemetry_partitions(DATE '2042-01-01',1)",
                    ):
                        with pytest.raises(DBAPIError) as error:
                            async with session.begin_nested():
                                await session.execute(text(sql))
                        assert error.value.orig.sqlstate == '42501'
                    assert await session.scalar(text('SELECT count(*) FROM public.alembic_version')) == 1
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()
