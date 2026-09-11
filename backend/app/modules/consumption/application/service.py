from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import insert, select

from app.core.database.scope import RecordNotFoundError, VersionConflictError
from app.core.events.orm import EventLog
from app.modules.authentication.infrastructure.authorization import require_permission
from app.modules.consumption.infrastructure.orm import Consumption
from app.modules.consumption.schemas.workflow import ConsumptionData, ReceiptData
from app.modules.fleet.application.delivery_service import DeliveryService
from app.modules.fleet.infrastructure.orm import Delivery, DeliveryItem, SchoolReceiving
from app.modules.master.infrastructure.orm import School
from app.modules.packaging.application.service import timer
from app.modules.production.infrastructure.orm import Package, ProductionBatch
from app.modules.traceability.infrastructure.orm import AssetMovement, AssetRelationship
from app.modules.traceability.infrastructure.registry import sync_source


class SchoolWorkflowConflictError(Exception):
    pass


class SchoolWorkflowService(DeliveryService):
    @staticmethod
    def receipt_data(row):
        return dict(row, discrepancy_quantity=None if row['expected_quantity'] is None or row['received_quantity'] is None
                    else row['expected_quantity'] - row['received_quantity'])

    async def read_record(self, kind, identifier):
        model, key, permission = self.config(kind)
        await require_permission(self.db, self.scope, permission + '.Read')
        result = await self.row(model, key, identifier)
        return self.receipt_data(result) if kind == 'receipt' else result

    @staticmethod
    def config(kind):
        return (SchoolReceiving, 'school_receiving_id', 'SchoolReceiving') if kind == 'receipt' else (Consumption, 'consumption_id', 'Consumption')

    async def list_records(self, kind, offset, limit, package_id=None, school=None, delivery_id=None):
        model, key, permission = self.config(kind)
        await require_permission(self.db, self.scope, permission + '.Read')
        query = select(model.__table__).where(*self.visible(model))
        if package_id is not None:
            query = query.where((model.package if kind == 'receipt' else model.package_id) == package_id)
        if kind == 'receipt':
            for field, value in (('school', school), ('delivery_id', delivery_id)):
                if value is not None:
                    query = query.where(getattr(model, field) == value)
        rows = (await self.db.execute(query.order_by(model.created_at.desc(), getattr(model, key).desc())
            .offset(offset).limit(limit + 1))).mappings().all()
        return {'items': [self.receipt_data(r) if kind == 'receipt' else dict(r) for r in rows[:limit]],
                'offset': offset, 'limit': limit, 'next_offset': offset + limit if len(rows) > limit else None}

    async def reference(self, model, key, identifier, lock=False):
        try:
            return await self.row(model, key, identifier, lock=lock)
        except RecordNotFoundError:
            raise SchoolWorkflowConflictError('Reference unavailable in tenant') from None

    async def receive(self, payload):
        await require_permission(self.db, self.scope, 'SchoolReceiving.Write')
        # Same school -> delivery -> package ordering as delivery completion.
        await self.reference(School, 'school_id', payload.school, lock=True)
        delivery = await self.reference(Delivery, 'delivery_id', payload.delivery_id, lock=True)
        manifest = await self.db.scalar(select(DeliveryItem.delivery_item_id).where(*self.visible(DeliveryItem),
            DeliveryItem.delivery_id == payload.delivery_id, DeliveryItem.package_id == payload.package,
            DeliveryItem.school_id == payload.school))
        if manifest is None or delivery['status'] != 'COMPLETED' or delivery['arrival_time'] is None:
            raise SchoolWorkflowConflictError('Completed delivery and matching package/school manifest required')
        package = await self.reference(Package, 'package_id', payload.package, lock=True)
        if package['version'] != payload.expected_version:
            raise VersionConflictError()
        if package['status'] != 'DELIVERED' or package['quantity'] is None:
            raise SchoolWorkflowConflictError('Delivered package with known quantity required')
        if await self.db.scalar(select(SchoolReceiving.school_receiving_id).where(
                SchoolReceiving.tenant_id == self.scope.tenant_id, SchoolReceiving.package == payload.package).limit(1)):
            raise SchoolWorkflowConflictError('Package already has a receiving decision')
        now = datetime.now(UTC)
        if now < delivery['arrival_time']:
            raise SchoolWorkflowConflictError('Receiving cannot precede delivery arrival')
        production = await self.row(ProductionBatch, 'production_batch_id', package['production_batch_id'])
        state = timer(production, package, now)
        quantity = payload.received_quantity
        if quantity > package['quantity'] or (payload.condition == 'MISSING') != (quantity == 0):
            raise SchoolWorkflowConflictError('Quantity must not exceed manifest; MISSING requires zero and other conditions positive quantity')
        if payload.accepted and (payload.condition != 'GOOD' or state['timer_status'] not in ('SAFE', 'WARNING')):
            raise SchoolWorkflowConflictError('Acceptance requires GOOD condition and unexpired known holding policy')
        if (not payload.accepted or quantity != package['quantity']) and not payload.notes:
            raise SchoolWorkflowConflictError('Rejection or quantity discrepancy requires notes')
        identifier = uuid4()
        values = payload.model_dump(exclude={'expected_version'})
        await self.db.execute(insert(SchoolReceiving).values(school_receiving_id=identifier, received_time=now,
            expected_quantity=package['quantity'], timer_status=state['timer_status'],
            uom=(production['recipe_snapshot'] or {}).get('uom'), created_at=now, updated_at=now, **values, **self.audit))
        school_asset = await sync_source(self.db, self.scope, 'SCHOOL', payload.school)
        asset = await self.package_status(package, 'RECEIVED' if payload.accepted else 'REJECTED', now)
        if payload.accepted:
            await self.db.execute(insert(AssetRelationship).values(relationship_uuid=uuid4(),
                parent_uuid=asset['asset_uuid'], child_uuid=school_asset['asset_uuid'], relationship_type='RECEIVED', **self.audit))
        await self.movement(asset, school_asset, 'SCHOOL_RECEIVING', now, identifier)
        result = self.receipt_data(await self.row(SchoolReceiving, 'school_receiving_id', identifier))
        await self.record_event('school_receiving.recorded', 'SCHOOL_RECEIVING', identifier, 'school_receiving', ReceiptData, result)
        return result

    async def consume(self, payload):
        await require_permission(self.db, self.scope, 'Consumption.Write')
        receipt = (await self.db.execute(select(SchoolReceiving.__table__).where(*self.visible(SchoolReceiving),
            SchoolReceiving.package == payload.package_id, SchoolReceiving.accepted.is_(True)))).mappings().one_or_none()
        if receipt is None or receipt['received_quantity'] is None:
            raise SchoolWorkflowConflictError('Accepted school receiving with known quantity required')
        await self.reference(School, 'school_id', receipt['school'], lock=True)
        package = await self.reference(Package, 'package_id', payload.package_id, lock=True)
        if package['version'] != payload.expected_version:
            raise VersionConflictError()
        if package['status'] != 'RECEIVED':
            raise SchoolWorkflowConflictError('Package must be RECEIVED and not finalized')
        if payload.consumed_quantity + payload.discarded_quantity != receipt['received_quantity']:
            raise SchoolWorkflowConflictError('Consumed plus discarded quantity must equal received quantity')
        now = datetime.now(UTC)
        if now < receipt['received_time']:
            raise SchoolWorkflowConflictError('Consumption cannot precede school receiving')
        production = await self.row(ProductionBatch, 'production_batch_id', package['production_batch_id'])
        state = timer(production, package, now)
        safe = state['timer_status'] in ('SAFE', 'WARNING') if payload.consumed_quantity > 0 else None
        if (payload.discarded_quantity > 0 or safe is False) and not payload.notes:
            raise SchoolWorkflowConflictError('Discard or consumption outside holding policy requires notes')
        identifier = uuid4()
        await self.db.execute(insert(Consumption).values(consumption_id=identifier, school_receiving_id=receipt['school_receiving_id'],
            consumed_at=now, remaining_minutes=state['remaining_minutes'], safe=safe, timer_status=state['timer_status'],
            uom=receipt['uom'], created_at=now, updated_at=now, **payload.model_dump(exclude={'expected_version'}), **self.audit))
        school_asset = await sync_source(self.db, self.scope, 'SCHOOL', receipt['school'])
        asset = await self.package_status(package, 'CONSUMED' if payload.consumed_quantity > 0 else 'DISCARDED', now)
        consumption_asset = await sync_source(self.db, self.scope, 'CONSUMPTION', identifier)
        if payload.consumed_quantity > 0:
            await self.db.execute(insert(AssetRelationship).values(relationship_uuid=uuid4(), parent_uuid=asset['asset_uuid'],
                child_uuid=consumption_asset['asset_uuid'], relationship_type='CONSUMED', **self.audit))
            await self.movement(asset, school_asset, 'CONSUMED', now, identifier)
        if payload.discarded_quantity > 0:
            await self.movement(asset, school_asset, 'DISCARD', now, identifier)
        result = await self.row(Consumption, 'consumption_id', identifier)
        await self.record_event('consumption.recorded', 'CONSUMPTION', identifier, 'consumption', ConsumptionData, result)
        return result

    async def movement(self, asset, school, kind, now, identifier):
        await self.db.execute(insert(AssetMovement).values(movement_id=uuid4(), asset_type='PACKAGE',
            asset_uuid=asset['asset_uuid'], movement_type=kind, from_location=school['asset_uuid'],
            to_location=school['asset_uuid'] if kind == 'SCHOOL_RECEIVING' else None,
            operator=self.scope.actor_id, movement_time=now, remarks=str(identifier), **self.audit))

    async def record_event(self, name, entity_type, identifier, key, schema, result):
        await self.db.execute(insert(EventLog).values(event_uuid=uuid4(), event_type=name, entity_type=entity_type,
            entity_uuid=identifier, payload={'schema_version': 1, 'actor_id': str(self.scope.actor_id),
                key: schema.model_validate(result).model_dump(mode='json')}, **self.audit))
