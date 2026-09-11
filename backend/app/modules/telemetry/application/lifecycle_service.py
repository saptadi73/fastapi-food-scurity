from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.scope import ActorScope, RecordNotFoundError
from app.modules.authentication.infrastructure.authorization import require_permission
from app.modules.telemetry.infrastructure.orm import (
    AlarmAcknowledgment,
    AlarmLog,
    DeviceSession,
    DeviceSessionEnd,
)


class CompletionConflictError(Exception):
    """A session already has a different immutable end time."""


class TelemetryLifecycleService:
    """Scoped evidence reads/completions. Caller owns transaction and trusted identity."""

    def __init__(self, session: AsyncSession, scope: ActorScope):
        self.session, self.scope = session, scope

    async def _authorize(self, permission):
        await require_permission(self.session, self.scope, permission)

    async def _lock_parent(self, model, key, identifier):
        table = model.__table__
        row = (await self.session.execute(select(table).where(
            table.c.tenant_id == self.scope.tenant_id, table.c[key] == identifier,
        ).with_for_update())).mappings().one_or_none()
        if row is None:
            raise RecordNotFoundError('Telemetry record not found')
        return row

    async def _alarm(self, identifier):
        a, ack = AlarmLog.__table__, AlarmAcknowledgment.__table__
        query = select(a, (a.c.acknowledged | ack.c.alarm_id.is_not(None)).label('effective_acknowledged'),
                       ack.c.acknowledged_at, ack.c.acknowledged_by, ack.c.acknowledgment_id).select_from(a.outerjoin(
            ack, (a.c.tenant_id == ack.c.tenant_id) & (a.c.alarm_id == ack.c.alarm_id),
        )).where(a.c.tenant_id == self.scope.tenant_id, a.c.alarm_id == identifier)
        row = (await self.session.execute(query)).mappings().one_or_none()
        if row is None:
            raise RecordNotFoundError('Telemetry record not found')
        return dict(row)

    async def _device_session(self, identifier):
        s, end = DeviceSession.__table__, DeviceSessionEnd.__table__
        effective = func.coalesce(s.c.disconnected_at, end.c.disconnected_at)
        query = select(s, effective.label('effective_disconnected_at'), effective.is_(None).label('is_open'),
                       end.c.session_end_id).select_from(s.outerjoin(
            end, (s.c.tenant_id == end.c.tenant_id) & (s.c.session_id == end.c.session_id),
        )).where(s.c.tenant_id == self.scope.tenant_id, s.c.session_id == identifier)
        row = (await self.session.execute(query)).mappings().one_or_none()
        if row is None:
            raise RecordNotFoundError('Telemetry record not found')
        return dict(row)

    async def get_alarm(self, identifier: UUID) -> dict:
        await self._authorize('Alarm.Read')
        return await self._alarm(identifier)

    async def get_session(self, identifier: UUID) -> dict:
        await self._authorize('DeviceSession.Read')
        return await self._device_session(identifier)

    async def acknowledge(self, identifier: UUID) -> dict:
        await self._authorize('Alarm.Acknowledge')
        parent = await self._lock_parent(AlarmLog, 'alarm_id', identifier)
        current = await self._alarm(identifier)
        if current['effective_acknowledged']:
            return current
        now = datetime.now(UTC)
        if now < parent['recorded_at']:
            raise ValueError('Alarm observation is in the future')
        await self.session.execute(insert(AlarmAcknowledgment.__table__).values(
            acknowledgment_id=uuid4(), tenant_id=self.scope.tenant_id, alarm_id=identifier,
            acknowledged_at=now, recorded_at=now, acknowledged_by=self.scope.actor_id,
            created_by=self.scope.actor_id, updated_by=self.scope.actor_id,
        ))
        return await self._alarm(identifier)

    async def close_session(self, identifier: UUID, *, disconnected_at: datetime) -> dict:
        await self._authorize('DeviceSession.Close')
        if not isinstance(disconnected_at, datetime) or disconnected_at.tzinfo is None or disconnected_at.utcoffset() is None:
            raise ValueError('Timezone-aware disconnected_at required')
        disconnected_at = disconnected_at.astimezone(UTC)
        parent = await self._lock_parent(DeviceSession, 'session_id', identifier)
        if disconnected_at < parent['connected_at']:
            raise ValueError('Disconnection precedes connection')
        current = await self._device_session(identifier)
        if current['effective_disconnected_at'] is not None:
            if current['effective_disconnected_at'] != disconnected_at:
                raise CompletionConflictError('Session already ended at a different time')
            return current
        now = datetime.now(UTC)
        if disconnected_at > now:
            raise ValueError('Disconnection cannot be in the future')
        await self.session.execute(insert(DeviceSessionEnd.__table__).values(
            session_end_id=uuid4(), tenant_id=self.scope.tenant_id, session_id=identifier,
            disconnected_at=disconnected_at, recorded_at=now,
            created_by=self.scope.actor_id, updated_by=self.scope.actor_id,
        ))
        return await self._device_session(identifier)
