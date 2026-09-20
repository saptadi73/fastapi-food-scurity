from uuid import UUID, uuid4

from sqlalchemy import Numeric, cast, func, insert, select, update

from app.core.database.scope import ActorScope, RecordNotFoundError, VersionConflictError
from app.modules.authentication.infrastructure.authorization import require_permission
from app.modules.master.application.master_deletion import soft_delete_master
from app.modules.master.infrastructure.kitchen_repository import KitchenRepository
from app.modules.master.infrastructure.orm import (
    Device,
    Driver,
    Kitchen,
    School,
    Storage,
    StorageZone,
    Vehicle,
)
from app.modules.master.schemas.fleet import DeviceInput, DriverInput, VehicleInput
from app.modules.master.schemas.locations import KitchenInput, SchoolInput, StorageInput, ZoneInput
from app.modules.traceability.infrastructure.registry import sync_source


class LocationConflictError(Exception):
    pass


class LocationService:
    def __init__(self, db, scope: ActorScope, kind: str):
        self.db, self.scope, self.kind = db, scope, kind
        model, self.pk, self.permission, self.input_type = {
            'driver': (Driver, 'driver_id', 'Driver', DriverInput),
            'vehicle': (Vehicle, 'vehicle_id', 'Vehicle', VehicleInput),
            'school': (School, 'school_id', 'School', SchoolInput),
            'kitchen': (Kitchen, 'kitchen_id', 'Kitchen', KitchenInput),
            'storage': (Storage, 'storage_id', 'Storage', StorageInput),
            'zone': (StorageZone, 'zone_id', 'StorageZone', ZoneInput),
            'device': (Device, 'device_id', 'Device', DeviceInput),
        }[kind]
        self.table = model.__table__

    def _visible(self):
        return self.table.c.tenant_id == self.scope.tenant_id, self.table.c.deleted_at.is_(None)

    def _query(self):
        columns = [c for c in self.table.c if c.name != 'location']
        if self.kind in ('storage', 'vehicle'):
            columns += [cast(func.ST_Y(self.table.c.location), Numeric(9, 6)).label('latitude'),
                        cast(func.ST_X(self.table.c.location), Numeric(9, 6)).label('longitude')]
        return select(*columns).where(*self._visible())

    async def _get(self, identifier, *, lock=False):
        query = self._query().where(self.table.c[self.pk] == identifier)
        if lock:
            query = query.with_for_update()
        row = (await self.db.execute(query)).mappings().one_or_none()
        if row is None:
            raise RecordNotFoundError('Location not found')
        return dict(row)

    async def get(self, identifier: UUID):
        await require_permission(self.db, self.scope, f'{self.permission}.Read')
        return await self._get(identifier)

    async def list(self, *, offset=0, limit=20, parent_id=None, device_type=None):
        await require_permission(self.db, self.scope, f'{self.permission}.Read')
        query = self._query()
        if parent_id is not None:
            parent_column = {'storage': 'kitchen_id', 'school': 'kitchen_id', 'zone': 'storage_id',
                             'vehicle': 'driver_id', 'device': 'zone_id'}[self.kind]
            query = query.where(self.table.c[parent_column] == parent_id)
        if self.kind == 'device' and device_type is not None:
            query = query.where(self.table.c.device_type == device_type)
        rows = (await self.db.execute(query.order_by(self.table.c.created_at.desc(), self.table.c[self.pk].desc())
                                      .offset(offset).limit(limit + 1))).mappings().all()
        return {'items': [dict(r) for r in rows[:limit]], 'offset': offset, 'limit': limit,
                'next_offset': offset + limit if len(rows) > limit else None}

    async def _parent(self, values):
        if self.kind in ('kitchen', 'driver'):
            return
        if self.kind == 'vehicle':
            if values['driver_id'] is not None:
                driver = await self.db.scalar(select(Driver.driver_id).where(
                    Driver.driver_id == values['driver_id'], Driver.tenant_id == self.scope.tenant_id,
                    Driver.deleted_at.is_(None), Driver.status == 'ACTIVE').with_for_update(read=True))
                if driver is None:
                    raise LocationConflictError('Active driver in this tenant required')
            if values['gps_device'] is not None:
                device = await self.db.scalar(select(Device.device_id).where(
                    Device.device_id == values['gps_device'], Device.tenant_id == self.scope.tenant_id,
                    Device.deleted_at.is_(None), Device.status == 'ACTIVE', Device.device_type == 'GPS').with_for_update(read=True))
                if device is None:
                    raise LocationConflictError('Active GPS device in this tenant required')
            return
        if self.kind == 'device':
            if values['zone_id'] is not None:
                zone = await self.db.scalar(select(StorageZone.zone_id).where(
                    StorageZone.zone_id == values['zone_id'], StorageZone.tenant_id == self.scope.tenant_id,
                    StorageZone.deleted_at.is_(None), StorageZone.status == 'ACTIVE').with_for_update(read=True))
                if zone is None:
                    raise LocationConflictError('Active parent storage zone in this tenant required')
            return
        # Lock ancestors root-first, so operational parent changes cannot race child creation.
        if self.kind in ('storage', 'school'):
            kitchen_id = values['kitchen_id']
        else:
            kitchen_id = await self.db.scalar(select(Storage.storage_id).where(
                Storage.storage_id == values['storage_id'], Storage.tenant_id == self.scope.tenant_id,
                Storage.deleted_at.is_(None)))
        kitchen = await self.db.scalar(select(Kitchen.kitchen_id).where(
            Kitchen.kitchen_id == kitchen_id, Kitchen.tenant_id == self.scope.tenant_id,
            Kitchen.deleted_at.is_(None), Kitchen.status == 'ACTIVE').with_for_update(read=True))
        if kitchen is None:
            raise LocationConflictError('Active parent location in this tenant required')
        if self.kind == 'zone':
            storage = await self.db.scalar(select(Storage.storage_id).where(
                Storage.storage_id == values['storage_id'], Storage.tenant_id == self.scope.tenant_id,
                Storage.deleted_at.is_(None), Storage.status == 'ACTIVE').with_for_update(read=True))
            if storage is None:
                raise LocationConflictError('Active parent location in this tenant required')

    def _values(self, values):
        if self.kind not in ('storage', 'vehicle'):
            return values
        values = dict(values)
        lat, lon = values.pop('latitude'), values.pop('longitude')
        values['location'] = None if lat is None else func.ST_SetSRID(func.ST_MakePoint(float(lon), float(lat)), 4326)
        return values

    async def save(self, values, *, identifier=None, expected_version=None):
        await require_permission(self.db, self.scope, f'{self.permission}.Write')
        values = self.input_type.model_validate(values).model_dump()
        await self._parent(values)
        if identifier is not None:
            current = await self._get(identifier, lock=True)
            if current['version'] != expected_version:
                raise VersionConflictError('Location changed; reload before retrying')
            parent = {'storage': 'kitchen_id', 'school': 'kitchen_id', 'zone': 'storage_id'}.get(self.kind)
            if parent and current[parent] != values[parent]:
                raise LocationConflictError('Parent location cannot be changed')
        if self.kind == 'kitchen':
            repo = KitchenRepository(self.db, self.scope)
            row = await repo.create(values) if identifier is None else await repo.update(identifier, values, expected_version=expected_version)
            return await self._get(row['kitchen_id'])
        fields = self._values(values)
        if identifier is None:
            identifier = uuid4()
            await self.db.execute(insert(self.table).values(**fields, **{self.pk: identifier}, tenant_id=self.scope.tenant_id,
                created_by=self.scope.actor_id, updated_by=self.scope.actor_id, version=1))
        else:
            if self.kind in ('storage', 'school', 'zone'):
                fields.pop('kitchen_id' if self.kind in ('storage', 'school') else 'storage_id')
            await self.db.execute(update(self.table).where(*self._visible(), self.table.c[self.pk] == identifier,
                self.table.c.version == expected_version).values(**fields, updated_by=self.scope.actor_id,
                updated_at=func.clock_timestamp(), version=self.table.c.version + 1))
        if self.kind in ('storage', 'school', 'vehicle', 'device'):
            await sync_source(self.db, self.scope, self.kind.upper(), identifier)
        return await self._get(identifier)


    async def delete(self, identifier, *, expected_version):
        await require_permission(self.db, self.scope, f'{self.permission}.Delete')
        if type(expected_version) is not int or expected_version < 1:
            raise ValueError('Positive expected_version required')
        current = await self._get(identifier, lock=True)
        if current['version'] != expected_version:
            raise VersionConflictError('Record changed; reload before retrying')
        return await soft_delete_master(self.db, self.scope, self.table, self.pk, current)
