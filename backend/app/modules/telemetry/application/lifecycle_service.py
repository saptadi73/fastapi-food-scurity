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

    def _alarm_query(self):
        a, ack = AlarmLog.__table__, AlarmAcknowledgment.__table__
        return select(a, (a.c.acknowledged | ack.c.alarm_id.is_not(None)).label('effective_acknowledged'),
                       ack.c.acknowledged_at, ack.c.acknowledged_by, ack.c.acknowledgment_id).select_from(a.outerjoin(
            ack, (a.c.tenant_id == ack.c.tenant_id) & (a.c.alarm_id == ack.c.alarm_id),
        )).where(a.c.tenant_id == self.scope.tenant_id)

    async def _alarm(self, identifier):
        query = self._alarm_query().where(AlarmLog.alarm_id == identifier)
        row = (await self.session.execute(query)).mappings().one_or_none()
        if row is None:
            raise RecordNotFoundError('Telemetry record not found')
        return dict(row)

    def _session_query(self):
        s, end = DeviceSession.__table__, DeviceSessionEnd.__table__
        effective = func.coalesce(s.c.disconnected_at, end.c.disconnected_at)
        return select(s, effective.label('effective_disconnected_at'), effective.is_(None).label('is_open'),
                       end.c.session_end_id).select_from(s.outerjoin(
            end, (s.c.tenant_id == end.c.tenant_id) & (s.c.session_id == end.c.session_id),
        )).where(s.c.tenant_id == self.scope.tenant_id)

    async def _device_session(self, identifier):
        query = self._session_query().where(DeviceSession.session_id == identifier)
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

    async def list_alarms(self, *, device_uuid: UUID | None = None,
                          acknowledged: bool | None = None, since: datetime | None = None,
                          until: datetime | None = None, offset: int = 0, limit: int = 20) -> dict:
        return await self._list('alarm', device_uuid, acknowledged, since, until, offset, limit)

    async def list_sessions(self, *, device_uuid: UUID | None = None,
                            is_open: bool | None = None, since: datetime | None = None,
                            until: datetime | None = None, offset: int = 0, limit: int = 20) -> dict:
        return await self._list('session', device_uuid, is_open, since, until, offset, limit)

    async def _list(self, kind, device_uuid, state, since, until, offset, limit):
        if type(offset) is not int or type(limit) is not int or offset < 0 or not 1 <= limit <= 100:
            raise ValueError('offset >= 0 and limit between 1 and 100 required')
        if device_uuid is not None and not isinstance(device_uuid, UUID):
            raise ValueError('device_uuid must be a UUID')
        if state is not None and type(state) is not bool:
            raise ValueError('Status filter must be boolean or None')
        for bound in (since, until):
            if bound is not None and (not isinstance(bound, datetime) or bound.tzinfo is None or bound.utcoffset() is None):
                raise ValueError('Timezone-aware date bounds required')
        if since is not None and until is not None and since >= until:
            raise ValueError('since must precede until')
        if kind == 'alarm':
            await self._authorize('Alarm.Read')
            query = self._alarm_query()
            time, key = AlarmLog.recorded_at, AlarmLog.alarm_id
            device, status = AlarmLog.device_uuid, query.selected_columns.effective_acknowledged
        else:
            await self._authorize('DeviceSession.Read')
            query = self._session_query()
            time, key = DeviceSession.connected_at, DeviceSession.session_id
            device, status = DeviceSession.device_uuid, query.selected_columns.is_open
        if device_uuid is not None:
            query = query.where(device == device_uuid)
        if state is not None:
            query = query.where(status == state)
        if since is not None:
            query = query.where(time >= since)
        if until is not None:
            query = query.where(time < until)
        rows = (await self.session.execute(query.order_by(time.desc(), key.desc()).offset(offset).limit(limit + 1))).mappings().all()
        return {'items': [dict(row) for row in rows[:limit]], 'offset': offset, 'limit': limit,
                'next_offset': offset + limit if len(rows) > limit else None}

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
