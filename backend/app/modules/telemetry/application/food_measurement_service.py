from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import insert, select

from app.core.events.orm import EventLog
from app.modules.authentication.infrastructure.authorization import require_permission
from app.modules.master.infrastructure.orm import Device
from app.modules.telemetry.infrastructure.orm import TemperatureLog


class FoodTemperatureMeasurementError(Exception):
    pass


class FoodTemperatureMeasurementService:
    def __init__(self, db, scope):
        self.db, self.scope = db, scope

    async def latest(self, payload):
        await require_permission(self.db, self.scope, 'FoodTemperature.Read')
        device = (await self.db.execute(select(Device.__table__).where(
            Device.tenant_id == self.scope.tenant_id, Device.device_id == payload.device_id,
            Device.deleted_at.is_(None)).with_for_update(read=True))).mappings().one_or_none()
        if device is None:
            raise FoodTemperatureMeasurementError('Food temperature device not found in tenant')
        if device['status'] != 'ACTIVE' or device['device_type'] != 'FOOD_TEMPERATURE':
            raise FoodTemperatureMeasurementError('Active FOOD_TEMPERATURE device required')
        if device['zone_id'] is not None:
            raise FoodTemperatureMeasurementError('Food probe must not be assigned to a storage zone')
        sample = (await self.db.execute(select(TemperatureLog.__table__).where(
            TemperatureLog.tenant_id == self.scope.tenant_id,
            TemperatureLog.device_uuid == device['device_uuid'],
            TemperatureLog.storage_uuid.is_(None), TemperatureLog.unit == 'C',
            TemperatureLog.deleted_at.is_(None),
        ).order_by(TemperatureLog.recorded_at.desc(), TemperatureLog.temperature_log_id.desc()).limit(1)
        )).mappings().one_or_none()
        if sample is None:
            raise FoodTemperatureMeasurementError('Food probe has no unbound Celsius sample')
        now = datetime.now(UTC)
        age = int((now - sample['recorded_at']).total_seconds())
        if age < -5:
            raise FoodTemperatureMeasurementError('Latest food probe sample is dated in the future')
        if age > payload.maximum_age_seconds:
            raise FoodTemperatureMeasurementError(
                f'Latest food probe sample is stale ({age} seconds; maximum {payload.maximum_age_seconds})')
        age = max(age, 0)
        result = {
            'device_id': device['device_id'], 'device_uuid': device['device_uuid'],
            'device_name': device['device_name'], 'temperature_log_id': sample['temperature_log_id'],
            'temperature': str(sample['temperature']), 'unit': sample['unit'],
            'recorded_at': sample['recorded_at'], 'age_seconds': age,
            'context_type': payload.context_type, 'context_id': payload.context_id, 'valid': True,
        }
        audit = {'tenant_id': self.scope.tenant_id, 'created_by': self.scope.actor_id,
                 'updated_by': self.scope.actor_id}
        await self.db.execute(insert(EventLog).values(
            event_uuid=uuid4(), event_type='food_temperature.sample_selected',
            entity_type=payload.context_type,
            entity_uuid=payload.context_id or sample['temperature_log_id'],
            payload={'schema_version': 1, 'actor_id': str(self.scope.actor_id),
                     'context_type': payload.context_type,
                     'context_id': None if payload.context_id is None else str(payload.context_id),
                     'device_id': str(device['device_id']),
                     'temperature_log_id': str(sample['temperature_log_id']),
                     'temperature': str(sample['temperature']), 'unit': sample['unit'],
                     'recorded_at': sample['recorded_at'].isoformat(), 'age_seconds': age},
            **audit))
        return result
