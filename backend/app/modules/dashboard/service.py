from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.scope import ActorScope
from app.modules.authentication.infrastructure.authorization import require_permission
from app.modules.complaint.infrastructure.orm import Complaint
from app.modules.fleet.infrastructure.orm import Delivery
from app.modules.master.infrastructure.orm import Driver, Storage, StorageZone, Vehicle
from app.modules.notification.infrastructure.orm import NotificationOutbox
from app.modules.production.infrastructure.orm import Package, ProductionBatch
from app.modules.receiving.infrastructure.orm import RawMaterialBatch, StockEntry
from app.modules.recall.infrastructure.orm import Recall
from app.modules.telemetry.infrastructure.orm import AlarmLog, GPSLog, HoldingLog, TemperatureLog
from app.modules.traceability.infrastructure.orm import AssetMovement


class DashboardService:
    def __init__(self, session: AsyncSession, scope: ActorScope):
        self.session, self.scope = session, scope

    def visible(self, model):
        return model.tenant_id == self.scope.tenant_id, model.deleted_at.is_(None)

    async def count(self, model, *conditions):
        return await self.session.scalar(select(func.count()).select_from(model).where(
            *self.visible(model), *conditions,
        ))

    async def home(self):
        await require_permission(self.session, self.scope, 'Dashboard.Read')
        return {
            'complaints_open': await self.count(Complaint),
            'recalls_open': await self.count(Recall, Recall.completed_at.is_(None)),
            'deliveries_in_transit': await self.count(Delivery, Delivery.status == 'IN_TRANSIT'),
            'packages_recalled': await self.count(Package, Package.status == 'RECALLED'),
            'packages_delivered': await self.count(Package, Package.status == 'DELIVERED'),
            'packages_received': await self.count(Package, Package.status == 'RECEIVED'),
            'packages_consumed': await self.count(Package, Package.status == 'CONSUMED'),
            'packages_discarded': await self.count(Package, Package.status == 'DISCARDED'),
            'production_completed': await self.count(ProductionBatch, ProductionBatch.status == 'COMPLETED'),
            'raw_batches_available': await self.count(RawMaterialBatch, RawMaterialBatch.status == 'ACCEPTED'),
        }

    async def storage(self):
        await require_permission(self.session, self.scope, 'Dashboard.Read')
        return {
            'storages_active': await self.count(Storage, Storage.status == 'ACTIVE'),
            'storage_zones': await self.count(StorageZone),
            'raw_batches_accepted': await self.count(RawMaterialBatch, RawMaterialBatch.status == 'ACCEPTED'),
            'stock_entries': await self.count(StockEntry),
            'temperature_logs': await self.count(TemperatureLog),
        }

    async def storage_temperatures(self, *, offset=0, limit=20):
        await require_permission(self.session, self.scope, 'Dashboard.Read')
        storages = (await self.session.execute(select(Storage.__table__).where(
            *self.visible(Storage), Storage.status == 'ACTIVE')
            .order_by(Storage.storage_name, Storage.storage_id)
            .offset(offset).limit(limit + 1))).mappings().all()
        items = []
        for storage in storages[:limit]:
            latest = (await self.session.execute(select(TemperatureLog.__table__).where(
                *self.visible(TemperatureLog), TemperatureLog.storage_uuid == storage['storage_id'])
                .order_by(TemperatureLog.recorded_at.desc()).limit(1))).mappings().one_or_none()
            temperature = None if latest is None else latest['temperature']
            if temperature is None:
                status = 'NO_DATA'
            elif latest['unit'] != 'C':
                status = 'UNSUPPORTED_UNIT'
            elif storage['temperature_min'] is not None and temperature < storage['temperature_min']:
                status = 'LOW'
            elif storage['temperature_max'] is not None and temperature > storage['temperature_max']:
                status = 'HIGH'
            else:
                status = 'OK'
            items.append({
                'storage_id': storage['storage_id'], 'storage_name': storage['storage_name'],
                'storage_type': storage['storage_type'], 'temperature_min': storage['temperature_min'],
                'temperature_max': storage['temperature_max'],
                'device_uuid': None if latest is None else latest['device_uuid'],
                'temperature_log_id': None if latest is None else latest['temperature_log_id'],
                'recorded_at': None if latest is None else latest['recorded_at'],
                'temperature': temperature, 'unit': None if latest is None else latest['unit'],
                'status': status,
            })
        return {'items': items, 'offset': offset, 'limit': limit,
                'next_offset': offset + limit if len(storages) > limit else None}

    async def fleet(self):
        await require_permission(self.session, self.scope, 'Dashboard.Read')
        return {
            'vehicles_active': await self.count(Vehicle, Vehicle.status == 'ACTIVE'),
            'drivers_active': await self.count(Driver, Driver.status == 'ACTIVE'),
            'deliveries_created': await self.count(Delivery, Delivery.status == 'CREATED'),
            'deliveries_in_transit': await self.count(Delivery, Delivery.status == 'IN_TRANSIT'),
            'deliveries_completed': await self.count(Delivery, Delivery.status == 'COMPLETED'),
            'gps_logs': await self.count(GPSLog),
        }

    async def holding(self):
        await require_permission(self.session, self.scope, 'Dashboard.Read')
        return {
            'packages_created': await self.count(Package, Package.status == 'CREATED'),
            'packages_packaged': await self.count(Package, Package.status == 'PACKAGED'),
            'packages_released': await self.count(Package, Package.status == 'RELEASED'),
            'packages_expired': await self.count(Package, Package.status == 'EXPIRED'),
            'packages_recalled': await self.count(Package, Package.status == 'RECALLED'),
            'holding_logs': await self.count(HoldingLog),
            'alarms_open': await self.count(AlarmLog, AlarmLog.acknowledged.is_(False)),
        }

    async def recall(self):
        await require_permission(self.session, self.scope, 'Dashboard.Read')
        return {
            'complaints_open': await self.count(Complaint),
            'recalls_open': await self.count(Recall, Recall.completed_at.is_(None)),
            'recalls_completed': await self.count(Recall, Recall.completed_at.is_not(None)),
            'packages_recalled': await self.count(Package, Package.status == 'RECALLED'),
            'recall_movements': await self.count(AssetMovement, AssetMovement.movement_type == 'RECALL'),
        }

    async def notifications(self):
        await require_permission(self.session, self.scope, 'Dashboard.Read')
        return {
            'pending': await self.count(NotificationOutbox, NotificationOutbox.status == 'PENDING'),
            'sent': await self.count(NotificationOutbox, NotificationOutbox.status == 'SENT'),
            'failed': await self.count(NotificationOutbox, NotificationOutbox.status == 'FAILED'),
            'cancelled': await self.count(NotificationOutbox, NotificationOutbox.status == 'CANCELLED'),
            'dashboard_pending': await self.count(
                NotificationOutbox, NotificationOutbox.status == 'PENDING',
                NotificationOutbox.channel == 'DASHBOARD'),
            'email_pending': await self.count(
                NotificationOutbox, NotificationOutbox.status == 'PENDING',
                NotificationOutbox.channel == 'EMAIL'),
            'whatsapp_pending': await self.count(
                NotificationOutbox, NotificationOutbox.status == 'PENDING',
                NotificationOutbox.channel == 'WHATSAPP'),
            'telegram_pending': await self.count(
                NotificationOutbox, NotificationOutbox.status == 'PENDING',
                NotificationOutbox.channel == 'TELEGRAM'),
        }
