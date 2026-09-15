from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.scope import ActorScope, RecordNotFoundError
from app.modules.authentication.infrastructure.authorization import require_permission
from app.modules.master.infrastructure.orm import Device, Storage, Vehicle
from app.modules.telemetry.infrastructure.orm import GPSLog, TemperatureLog


class TelemetryIngestionConflictError(Exception):
    pass


class TelemetryIngestionService:
    def __init__(self, session: AsyncSession, scope: ActorScope):
        self.session, self.scope = session, scope

    async def row(self, model, key, identifier):
        row = (await self.session.execute(select(model.__table__).where(
            model.tenant_id == self.scope.tenant_id,
            getattr(model, key) == identifier,
            model.deleted_at.is_(None),
        ).with_for_update(read=True))).mappings().one_or_none()
        if row is None:
            raise RecordNotFoundError()
        return row

    async def gps(self, payload):
        await require_permission(self.session, self.scope, 'Telemetry.Ingest')
        vehicle = await self.row(Vehicle, 'vehicle_id', payload.vehicle_uuid)
        if vehicle['status'] != 'ACTIVE':
            raise TelemetryIngestionConflictError('Active vehicle required')
        recorded_at = payload.recorded_at or datetime.now(UTC)
        result = (await self.session.execute(insert(GPSLog.__table__).values(
            gps_log_id=uuid4(), tenant_id=self.scope.tenant_id, recorded_at=recorded_at,
            mqtt_message_id=None, vehicle_uuid=payload.vehicle_uuid, latitude=payload.latitude,
            longitude=payload.longitude, speed=payload.speed, heading=payload.heading,
            altitude=payload.altitude, hdop=payload.hdop, satellite=payload.satellite,
            created_by=self.scope.actor_id, updated_by=self.scope.actor_id,
        ).returning(GPSLog.__table__))).mappings().one()
        return dict(result)

    async def temperature(self, payload):
        await require_permission(self.session, self.scope, 'Telemetry.Ingest')
        device = await self.row(Device, 'device_uuid', payload.device_uuid)
        if device['status'] not in ('ACTIVE', 'REGISTERED'):
            raise TelemetryIngestionConflictError('Active or registered device required')
        if payload.storage_uuid is not None:
            storage = await self.row(Storage, 'storage_id', payload.storage_uuid)
            if storage['status'] != 'ACTIVE':
                raise TelemetryIngestionConflictError('Active storage required')
        recorded_at = payload.recorded_at or datetime.now(UTC)
        result = (await self.session.execute(insert(TemperatureLog.__table__).values(
            temperature_log_id=uuid4(), tenant_id=self.scope.tenant_id, recorded_at=recorded_at,
            mqtt_message_id=None, device_uuid=payload.device_uuid, storage_uuid=payload.storage_uuid,
            temperature=payload.temperature, unit=payload.unit,
            created_by=self.scope.actor_id, updated_by=self.scope.actor_id,
        ).returning(TemperatureLog.__table__))).mappings().one()
        return dict(result)
