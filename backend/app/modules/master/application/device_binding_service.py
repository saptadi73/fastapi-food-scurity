from uuid import uuid4

from sqlalchemy import func, insert, select, update

from app.core.database.scope import ActorScope, RecordNotFoundError, VersionConflictError
from app.modules.authentication.infrastructure.authorization import require_permission
from app.modules.master.application.master_deletion import soft_delete_master
from app.modules.master.infrastructure.orm import Device, DeviceBinding, Vehicle
from app.modules.master.schemas.fleet import DeviceBindingInput


class DeviceBindingConflictError(Exception):
    pass


class DeviceBindingService:
    def __init__(self, db, scope):
        self.db = db
        self.scope = scope
        self.table = DeviceBinding.__table__

    def _visible(self):
        return self.table.c.tenant_id == self.scope.tenant_id, self.table.c.deleted_at.is_(None)

    async def _get(self, identifier, lock=False):
        query = select(self.table).where(*self._visible(), self.table.c.binding_id == identifier)
        if lock:
            query = query.with_for_update()
        row = (await self.db.execute(query)).mappings().one_or_none()
        if row is None:
            raise RecordNotFoundError('Device binding not found')
        return dict(row)

    async def get(self, identifier):
        await require_permission(self.db, self.scope, 'Device.Read')
        return await self._get(identifier)

    async def list(self, *, offset=0, limit=20, device_id=None, vehicle_id=None):
        await require_permission(self.db, self.scope, 'Device.Read')
        if type(offset) is not int or type(limit) is not int or offset < 0 or not 1 <= limit <= 100:
            raise ValueError('Invalid pagination')
        query = select(self.table).where(*self._visible())
        if device_id is not None:
            query = query.where(self.table.c.device_id == device_id)
        if vehicle_id is not None:
            query = query.where(self.table.c.vehicle_id == vehicle_id)
        rows = (await self.db.execute(query.order_by(self.table.c.created_at.desc(), self.table.c.binding_id.desc())
                                     .offset(offset).limit(limit + 1))).mappings().all()
        return {'items': [dict(r) for r in rows[:limit]], 'offset': offset, 'limit': limit,
                'next_offset': offset + limit if len(rows) > limit else None}

    async def _validate_parent(self, values):
        device = await self.db.scalar(select(Device.device_id).where(
            Device.device_id == values['device_id'], Device.tenant_id == self.scope.tenant_id,
            Device.deleted_at.is_(None), Device.status == 'ACTIVE', Device.device_type == 'GPS').with_for_update(read=True))
        if device is None:
            raise DeviceBindingConflictError('Active GPS device in this tenant required')
        vehicle = await self.db.scalar(select(Vehicle.vehicle_id).where(
            Vehicle.vehicle_id == values['vehicle_id'], Vehicle.tenant_id == self.scope.tenant_id,
            Vehicle.deleted_at.is_(None), Vehicle.status == 'ACTIVE').with_for_update(read=True))
        if vehicle is None:
            raise DeviceBindingConflictError('Active vehicle in this tenant required')

    async def save(self, values, *, identifier=None, expected_version=None):
        await require_permission(self.db, self.scope, 'Device.Write')
        values = DeviceBindingInput.model_validate(values).model_dump()
        if identifier is not None and (type(expected_version) is not int or expected_version < 1):
            raise ValueError('Positive expected_version required')
        await self._validate_parent(values)
        if identifier is None:
            identifier = uuid4()
            await self.db.execute(insert(self.table).values(**values, **{self.table.c.binding_id.name: identifier},
                tenant_id=self.scope.tenant_id, created_by=self.scope.actor_id, updated_by=self.scope.actor_id,
                version=1))
        else:
            current = await self._get(identifier, lock=True)
            if current['version'] != expected_version:
                raise VersionConflictError('Device binding changed; reload before retrying')
            await self.db.execute(update(self.table).where(*self._visible(), self.table.c.binding_id == identifier,
                self.table.c.version == expected_version).values(**values, updated_by=self.scope.actor_id,
                updated_at=func.clock_timestamp(), version=self.table.c.version + 1))
        return await self._get(identifier)

    async def delete(self, identifier, *, expected_version):
        await require_permission(self.db, self.scope, 'Device.Delete')
        if type(expected_version) is not int or expected_version < 1:
            raise ValueError('Positive expected_version required')
        current = await self._get(identifier, lock=True)
        if current['version'] != expected_version:
            raise VersionConflictError('Device binding changed; reload before retrying')
        return await soft_delete_master(self.db, self.scope, self.table, 'binding_id', current)
