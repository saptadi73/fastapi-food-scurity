from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import insert, or_, select, update

from app.core.database.scope import RecordNotFoundError, VersionConflictError
from app.core.events.orm import EventLog
from app.modules.authentication.infrastructure.authorization import require_permission
from app.modules.fleet.infrastructure.orm import Delivery, DeliveryItem
from app.modules.fleet.schemas.delivery import DeliveryDetail
from app.modules.master.infrastructure.orm import Driver, Kitchen, School, Vehicle
from app.modules.packaging.application.service import PackageService, timer
from app.modules.production.infrastructure.orm import Package, ProductionBatch
from app.modules.traceability.infrastructure.orm import AssetMovement, AssetRelationship
from app.modules.traceability.infrastructure.registry import sync_source


class DeliveryConflictError(Exception):
    pass


class DeliveryService(PackageService):
    async def parents(self, data, school_ids, active=True):
        # Driver before vehicle matches master vehicle update; then kitchen/schools.
        result = {}
        for model, key, identifier in ((Driver, 'driver_id', data['driver']),
                (Vehicle, 'vehicle_id', data['vehicle']), (Kitchen, 'kitchen_id', data['kitchen_id'])):
            try:
                row = await self.row(model, key, identifier, lock=True)
            except RecordNotFoundError:
                raise DeliveryConflictError('Delivery parents unavailable in this tenant') from None
            if active and row['status'] != 'ACTIVE':
                raise DeliveryConflictError('Active driver, vehicle, kitchen and schools required')
            result[key] = row
        for identifier in sorted(set(school_ids)):
            try:
                school = await self.row(School, 'school_id', identifier, lock=True)
            except RecordNotFoundError:
                raise DeliveryConflictError('Delivery parents unavailable in this tenant') from None
            if school['kitchen_id'] != data['kitchen_id']:
                raise DeliveryConflictError('Destination schools must belong to origin kitchen')
            if active and school['status'] != 'ACTIVE':
                raise DeliveryConflictError('Active driver, vehicle, kitchen and schools required')
        assigned = result['vehicle_id']['driver_id']
        if active and assigned is not None and assigned != data['driver']:
            raise DeliveryConflictError('Selected driver differs from vehicle assigned driver')
        return result

    async def manifest(self, identifier):
        return [dict(r) for r in (await self.db.execute(select(DeliveryItem.__table__).where(
            *self.visible(DeliveryItem), DeliveryItem.delivery_id == identifier)
            .order_by(DeliveryItem.package_id))).mappings()]

    async def detail(self, identifier):
        result = await self.row(Delivery, 'delivery_id', identifier)
        now = datetime.now(UTC)
        result['items'] = [dict(item, package=await self.projection(
            await self.row(Package, 'package_id', item['package_id']), now)) for item in await self.manifest(identifier)]
        return result

    async def get(self, identifier):
        await require_permission(self.db, self.scope, 'Delivery.Read')
        await self.row(Delivery, 'delivery_id', identifier, lock=True)
        return await self.detail(identifier)

    async def list(self, *, offset=0, limit=20, kitchen_id=None, vehicle=None, driver=None, status=None):
        await require_permission(self.db, self.scope, 'Delivery.Read')
        query = select(Delivery.__table__).where(*self.visible(Delivery))
        for key, value in (('kitchen_id', kitchen_id), ('vehicle', vehicle), ('driver', driver), ('status', status)):
            if value is not None:
                query = query.where(getattr(Delivery, key) == value)
        rows = (await self.db.execute(query.order_by(Delivery.created_at.desc(), Delivery.delivery_id.desc())
            .offset(offset).limit(limit + 1))).mappings().all()
        return {'items': [dict(r) for r in rows[:limit]], 'offset': offset, 'limit': limit,
                'next_offset': offset + limit if len(rows) > limit else None}

    async def available_resources(self, data, excluding=None):
        query = select(Delivery.delivery_id).where(*self.visible(Delivery),
            Delivery.status.in_(['CREATED', 'IN_TRANSIT']),
            or_(Delivery.vehicle == data['vehicle'], Delivery.driver == data['driver']))
        if excluding is not None:
            query = query.where(Delivery.delivery_id != excluding)
        if await self.db.scalar(query.limit(1)) is not None:
            raise DeliveryConflictError('Vehicle or driver already reserved by an active delivery')

    async def usable(self, package, kitchen_id, now, expected_status, eta=None):
        production = await self.row(ProductionBatch, 'production_batch_id', package['production_batch_id'])
        if production['kitchen'] != kitchen_id or production['status'] != 'COMPLETED' or package['quantity'] is None:
            raise DeliveryConflictError('Package must originate from completed production in origin kitchen')
        state = timer(production, package, now)
        if package['status'] != expected_status or state['timer_status'] not in ('SAFE', 'WARNING') or package['holding_finished_at'] is None:
            raise DeliveryConflictError('Package must be released and unexpired for dispatch')
        if eta is not None and (package['expired_at'] is None or eta >= package['expired_at']):
            raise DeliveryConflictError('Estimated arrival must precede every package holding deadline')
        return production

    async def package_status(self, package, status, now):
        await self.db.execute(update(Package).where(*self.visible(Package), Package.package_id == package['package_id'])
            .values(status=status, version=package['version'] + 1, updated_at=now, updated_by=self.scope.actor_id))
        return await sync_source(self.db, self.scope, 'PACKAGE', package['package_id'])

    async def create(self, payload):
        await require_permission(self.db, self.scope, 'Delivery.Write')
        data = payload.model_dump(exclude={'items'})
        await self.parents(data, [i.school_id for i in payload.items])
        await self.available_resources(data)
        now, checked = datetime.now(UTC), []
        for item in sorted(payload.items, key=lambda i: i.package_id):
            try:
                package = await self.row(Package, 'package_id', item.package_id, lock=True)
            except RecordNotFoundError:
                raise DeliveryConflictError('Package unavailable in this tenant') from None
            if package['version'] != item.expected_version:
                raise VersionConflictError()
            await self.usable(package, payload.kitchen_id, now, 'RELEASED')
            used = await self.db.scalar(select(DeliveryItem.delivery_id).join(Delivery,
                (Delivery.tenant_id == DeliveryItem.tenant_id) & (Delivery.delivery_id == DeliveryItem.delivery_id)).where(
                *self.visible(DeliveryItem), *self.visible(Delivery), DeliveryItem.package_id == item.package_id,
                Delivery.status != 'CANCELLED').limit(1))
            if used is not None:
                raise DeliveryConflictError('Package already assigned to a noncancelled delivery')
            checked.append((item, package))
        identifier = uuid4()
        await self.db.execute(insert(Delivery).values(delivery_id=identifier, **data, status='CREATED', **self.audit))
        for item, package in checked:
            await self.db.execute(insert(DeliveryItem).values(delivery_item_id=uuid4(), delivery_id=identifier,
                package_id=item.package_id, school_id=item.school_id, **self.audit))
            await self.package_status(package, 'ALLOCATED', now)
        await sync_source(self.db, self.scope, 'DELIVERY', identifier)
        result = await self.detail(identifier)
        await self.event('delivery.created', result)
        return result

    async def transition(self, identifier, payload, action):
        await require_permission(self.db, self.scope, {'depart': 'Delivery.Depart', 'complete': 'Delivery.Complete', 'cancel': 'Delivery.Cancel'}[action])
        initial = await self.row(Delivery, 'delivery_id', identifier)
        if initial['kitchen_id'] is None:
            raise DeliveryConflictError('Legacy delivery has no executable origin kitchen')
        items = await self.manifest(identifier)
        if not items:
            raise DeliveryConflictError('Delivery manifest cannot be empty')
        await self.parents(initial, [i['school_id'] for i in items], active=action == 'depart')
        current = await self.row(Delivery, 'delivery_id', identifier, lock=True)
        if current['version'] != payload.expected_version:
            raise VersionConflictError()
        required = 'IN_TRANSIT' if action == 'complete' else 'CREATED'
        if current['status'] != required:
            raise DeliveryConflictError(f'Delivery must be {required}')
        if action == 'depart':
            await self.available_resources(current, excluding=identifier)
        now = datetime.now(UTC)
        if action == 'depart' and payload.estimated_arrival_time <= now:
            raise DeliveryConflictError('Estimated arrival must be in the future at departure')
        packages = []
        for item in items:
            package = await self.row(Package, 'package_id', item['package_id'], lock=True)
            if action == 'depart':
                await self.usable(package, current['kitchen_id'], now, 'ALLOCATED', payload.estimated_arrival_time)
            elif package['status'] != ('IN_TRANSIT' if action == 'complete' else 'ALLOCATED'):
                raise DeliveryConflictError('Package state differs from delivery state')
            packages.append((item, package))
        changes = {'status': {'depart': 'IN_TRANSIT', 'complete': 'COMPLETED', 'cancel': 'CANCELLED'}[action],
                   'version': current['version'] + 1, 'updated_at': now, 'updated_by': self.scope.actor_id}
        if action == 'depart':
            changes.update(departure_time=now, estimated_arrival_time=payload.estimated_arrival_time)
        if action == 'complete':
            changes.update(arrival_time=now)
        await self.db.execute(update(Delivery).where(*self.visible(Delivery), Delivery.delivery_id == identifier).values(**changes))
        delivery_asset = await sync_source(self.db, self.scope, 'DELIVERY', identifier)
        vehicle = await sync_source(self.db, self.scope, 'VEHICLE', current['vehicle']) if action != 'cancel' else None
        origin = await sync_source(self.db, self.scope, 'KITCHEN', current['kitchen_id']) if action == 'depart' else None
        schools = {}
        if action == 'complete':
            for school_id in sorted({i['school_id'] for i in items}):
                schools[school_id] = await sync_source(self.db, self.scope, 'SCHOOL', school_id)
        for item, package in packages:
            if action == 'cancel':
                production = await self.row(ProductionBatch, 'production_batch_id', package['production_batch_id'])
                state = timer(production, package, now)
                status = 'RELEASED' if state['timer_status'] in ('SAFE', 'WARNING') else 'EXPIRED'
            else:
                status = 'IN_TRANSIT' if action == 'depart' else 'DELIVERED'
            asset = await self.package_status(package, status, now)
            if action == 'cancel':
                continue
            await self.db.execute(insert(AssetRelationship).values(relationship_uuid=uuid4(),
                parent_uuid=asset['asset_uuid'], child_uuid=delivery_asset['asset_uuid'] if action == 'depart' else schools[item['school_id']]['asset_uuid'],
                relationship_type='LOADED' if action == 'depart' else 'DELIVERED', **self.audit))
            await self.db.execute(insert(AssetMovement).values(movement_id=uuid4(), asset_type='PACKAGE',
                asset_uuid=asset['asset_uuid'], movement_type='VEHICLE_LOADING' if action == 'depart' else 'DELIVERY',
                from_location=origin['asset_uuid'] if action == 'depart' else vehicle['asset_uuid'],
                to_location=vehicle['asset_uuid'] if action == 'depart' else schools[item['school_id']]['asset_uuid'],
                operator=self.scope.actor_id, movement_time=now, remarks=str(item['delivery_item_id']), **self.audit))
        result = await self.detail(identifier)
        await self.event({'depart': 'delivery.departed', 'complete': 'delivery.completed', 'cancel': 'delivery.cancelled'}[action], result)
        return result

    async def event(self, name, detail):
        await self.db.execute(insert(EventLog).values(event_uuid=uuid4(), event_type=name, entity_type='DELIVERY',
            entity_uuid=detail['delivery_id'], payload={'schema_version': 1, 'actor_id': str(self.scope.actor_id),
                'delivery': DeliveryDetail.model_validate(detail).model_dump(mode='json')}, **self.audit))
