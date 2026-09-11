import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, insert, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.database.development_seed import seed_development, seed_id
from app.core.database.runtime_role import provision_runtime_role
from app.core.database.scope import ActorScope, RecordNotFoundError
from app.modules.authentication.infrastructure.authorization import PermissionDeniedError
from app.modules.authentication.infrastructure.orm import Permission, RolePermission
from app.modules.master.infrastructure.orm import Device, Tenant
from app.modules.telemetry.application.lifecycle_service import (
    CompletionConflictError,
    TelemetryLifecycleService,
)
from app.modules.telemetry.infrastructure.orm import (
    AlarmAcknowledgment,
    AlarmLog,
    DeviceSession,
    DeviceSessionEnd,
)

TEST_URL = os.environ.get('FSOS_TEST_DATABASE_URL', '')


@pytest.mark.skipif(not TEST_URL, reason='Migrated FSOS_TEST_DATABASE_URL required')
async def test_telemetry_lifecycle():
    assert (make_url(TEST_URL).database or '').startswith('fsos_test')
    engine = create_async_engine(TEST_URL)
    try:
        async with engine.connect() as c:
            transaction = await c.begin()
            try:
                async with AsyncSession(bind=c) as session:
                    await seed_development(session, environment='development')
                    tenant, actor, device = seed_id('tenant'), seed_id('actor'), seed_id('device-public')
                    service = TelemetryLifecycleService(session, ActorScope(tenant, actor))
                    now = datetime.now(UTC)
                    connected, ended = now - timedelta(hours=2), now - timedelta(hours=1)
                    alarm, imported_alarm, session_id, imported_session = (uuid4() for _ in range(4))
                    for identifier, acknowledged in ((alarm, False), (imported_alarm, True)):
                        await session.execute(insert(AlarmLog.__table__).values(
                            alarm_id=identifier, tenant_id=tenant, device_uuid=device, alarm_code='TEST',
                            severity='HIGH', recorded_at=connected, acknowledged=acknowledged,
                        ))
                    for identifier, end in ((session_id, None), (imported_session, ended)):
                        await session.execute(insert(DeviceSession.__table__).values(
                            session_id=identifier, tenant_id=tenant, device_uuid=device,
                            connected_at=connected, disconnected_at=end, recorded_at=connected,
                        ))
                    with pytest.raises(PermissionDeniedError):
                        await service.get_alarm(alarm)
                    with pytest.raises(PermissionDeniedError):
                        await service.acknowledge(alarm)
                    with pytest.raises(PermissionDeniedError):
                        await service.list_alarms()
                    with pytest.raises(PermissionDeniedError):
                        await service.list_sessions()

                    async def grant(code):
                        permission = uuid4()
                        await session.execute(insert(Permission.__table__).values(permission_id=permission, tenant_id=tenant, permission_code=code))
                        await session.execute(insert(RolePermission.__table__).values(role_permission_id=uuid4(), tenant_id=tenant,
                                                                                     role_id=seed_id('role'), permission_id=permission))

                    for code in ('Alarm.Read', 'DeviceSession.Read'):
                        await grant(code)
                    assert (await service.get_alarm(alarm))['effective_acknowledged'] is False
                    assert (await service.get_session(session_id))['is_open'] is True
                    assert [r['alarm_id'] for r in (await service.list_alarms(acknowledged=False))['items']] == [alarm]
                    assert [r['alarm_id'] for r in (await service.list_alarms(acknowledged=True))['items']] == [imported_alarm]
                    assert [r['session_id'] for r in (await service.list_sessions(is_open=True))['items']] == [session_id]
                    assert [r['session_id'] for r in (await service.list_sessions(is_open=False))['items']] == [imported_session]
                    with pytest.raises(PermissionDeniedError):
                        await service.acknowledge(alarm)
                    with pytest.raises(PermissionDeniedError):
                        await service.close_session(session_id, disconnected_at=ended)
                    for code in ('Alarm.Acknowledge', 'DeviceSession.Close'):
                        await grant(code)
                    first = await service.acknowledge(alarm)
                    assert first['effective_acknowledged'] is True and first['acknowledged'] is False
                    assert first['acknowledged_by'] == actor
                    assert await service.acknowledge(alarm) == first
                    imported = await service.acknowledge(imported_alarm)
                    assert imported['effective_acknowledged'] is True and imported['acknowledgment_id'] is None
                    assert imported['acknowledged_at'] is None  # do not invent imported metadata
                    naive = datetime(2026, 1, 1)  # noqa: DTZ001 - intentional invalid input
                    for invalid in (naive, connected - timedelta(seconds=1), now + timedelta(days=1)):
                        with pytest.raises(ValueError):
                            await service.close_session(session_id, disconnected_at=invalid)
                    closed = await service.close_session(session_id, disconnected_at=ended)
                    assert closed['is_open'] is False and closed['disconnected_at'] is None
                    assert closed['effective_disconnected_at'] == ended
                    assert await service.close_session(session_id, disconnected_at=ended) == closed
                    with pytest.raises(CompletionConflictError):
                        await service.close_session(session_id, disconnected_at=ended + timedelta(seconds=1))
                    imported = await service.close_session(imported_session, disconnected_at=ended)
                    assert imported['session_end_id'] is None and imported['is_open'] is False
                    assert await session.scalar(select(func.count()).select_from(AlarmAcknowledgment.__table__)) == 1
                    assert await session.scalar(select(func.count()).select_from(DeviceSessionEnd.__table__)) == 1
                    assert await session.scalar(select(DeviceSessionEnd.created_by)) == actor
                    # Evidence owned by another tenant must be indistinguishable from missing.
                    other = uuid4()
                    await session.execute(insert(Tenant.__table__).values(tenant_id=other, tenant_code=str(other), tenant_name='Other'))
                    other_device, foreign = uuid4(), uuid4()
                    await session.execute(insert(Device.__table__).values(device_id=uuid4(), device_uuid=other_device,
                                          tenant_id=other, device_name='Other', device_type='TEMPERATURE'))
                    await session.execute(insert(AlarmLog.__table__).values(alarm_id=foreign, tenant_id=other,
                                          device_uuid=other_device, alarm_code='OTHER', severity='HIGH', recorded_at=connected))
                    await session.execute(insert(DeviceSession.__table__).values(session_id=foreign, tenant_id=other,
                                          device_uuid=other_device, connected_at=connected, recorded_at=connected))
                    for identifier in (uuid4(), foreign):
                        with pytest.raises(RecordNotFoundError):
                            await service.get_alarm(identifier)
                        with pytest.raises(RecordNotFoundError):
                            await service.get_session(identifier)
                        with pytest.raises(RecordNotFoundError):
                            await service.acknowledge(identifier)
                        with pytest.raises(RecordNotFoundError):
                            await service.close_session(identifier, disconnected_at=ended)
                    # Shared projection: list filters include both imported and separately completed evidence.
                    for method, key, ids, status in (
                        (service.list_alarms, 'alarm_id', [alarm, imported_alarm], {'acknowledged': True}),
                        (service.list_sessions, 'session_id', [session_id, imported_session], {'is_open': False}),
                    ):
                        page = await method(limit=1, since=connected, until=ended, device_uuid=device, **status)
                        next_page = await method(limit=1, offset=page['next_offset'], **status)
                        assert page['next_offset'] == 1 and next_page['next_offset'] is None
                        assert [page['items'][0][key], next_page['items'][0][key]] == sorted(ids, reverse=True)
                        for row in (page['items'][0], next_page['items'][0]):
                            detail = await (service.get_alarm(row[key]) if key == 'alarm_id' else service.get_session(row[key]))
                            assert row == detail
                        assert (await method(offset=2))['items'] == []
                        assert (await method(until=connected))['items'] == []
                        assert (await method(since=connected + timedelta(microseconds=1)))['items'] == []
                        assert (await method(device_uuid=other_device))['items'] == []
                        assert (await method(device_uuid=uuid4()))['items'] == []
                        assert (await method(**{k: not v for k, v in status.items()}))['items'] == []
                    assert await session.scalar(select(func.count()).select_from(AlarmAcknowledgment)) == 1
                    assert await session.scalar(select(func.count()).select_from(DeviceSessionEnd)) == 1
                    await provision_runtime_role(c)
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    assert len((await service.list_alarms())['items']) == 2
                    assert len((await service.list_sessions())['items']) == 2
                    await c.execute(text('RESET ROLE'))
                    await session.execute(update(RolePermission.__table__).where(RolePermission.tenant_id == tenant).values(deleted_at=func.now()))
                    for method in (service.list_alarms, service.list_sessions):
                        with pytest.raises(PermissionDeniedError):
                            await method()
            finally:
                await transaction.rollback()
            assert await c.scalar(select(AlarmLog.alarm_id).where(AlarmLog.alarm_id == alarm)) is None
    finally:
        await engine.dispose()


@pytest.mark.parametrize('kwargs', [
    {'offset': -1}, {'offset': True}, {'limit': 0}, {'limit': 101}, {'limit': False},
    {'device_uuid': 'invalid'}, {'since': '2026-09-11'},
    {'until': datetime(2026, 1, 1)},  # noqa: DTZ001 - intentional invalid input
    {'since': datetime(2026, 1, 1, tzinfo=UTC), 'until': datetime(2026, 1, 1, tzinfo=UTC)},
])
async def test_telemetry_list_invalid_parameters(kwargs):
    service = TelemetryLifecycleService(None, ActorScope(uuid4(), uuid4()))
    for method in (service.list_alarms, service.list_sessions):
        with pytest.raises(ValueError):
            await method(**kwargs)


async def test_telemetry_list_strict_boolean_filters():
    service = TelemetryLifecycleService(None, ActorScope(uuid4(), uuid4()))
    with pytest.raises(ValueError):
        await service.list_alarms(acknowledged=1)
    with pytest.raises(ValueError):
        await service.list_sessions(is_open='false')
