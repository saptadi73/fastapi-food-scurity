from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import uuid4

from sqlalchemy import func, insert, select, update

from app.core.database.scope import RecordNotFoundError, VersionConflictError
from app.core.events.orm import EventLog
from app.modules.authentication.infrastructure.authorization import require_permission
from app.modules.master.infrastructure.orm import (
    Device,
    FoodItem,
    Kitchen,
    RawMaterial,
    Recipe,
    Storage,
)
from app.modules.production.infrastructure.orm import ProductionBatch, ProductionItem
from app.modules.production.schemas.production import ProductionDetail, RecipeSnapshot
from app.modules.receiving.application.service import ReceivingService
from app.modules.receiving.infrastructure.orm import (
    RawMaterialBatch,
    Receiving,
    ReceivingItem,
    StockEntry,
    StockIssue,
)
from app.modules.telemetry.infrastructure.orm import FoodSensorBinding
from app.modules.traceability.infrastructure.orm import (
    AssetMovement,
    AssetRelationship,
    DigitalAsset,
)
from app.modules.traceability.infrastructure.registry import sync_source


class ProductionConflictError(Exception):
    pass


class ProductionService(ReceivingService):
    def normalize_recipe_snapshot(self, snapshot):
        if snapshot is None:
            return None
        normalized = dict(snapshot)
        normalized.setdefault('schema_version', 1)
        normalized.setdefault('food_version', 1)
        normalized.setdefault('items', [])
        return normalized

    def normalize_production(self, row):
        data = dict(row)
        data['recipe_snapshot'] = self.normalize_recipe_snapshot(data.get('recipe_snapshot'))
        return data

    async def active(self, model, key, identifier):
        try:
            row = await self.row(model, key, identifier, lock=True)
        except RecordNotFoundError:
            raise ProductionConflictError('Active production references in this tenant required') from None
        if row['status'] != 'ACTIVE':
            raise ProductionConflictError('Active production references in this tenant required')
        return row

    async def detail(self, identifier):
        result = self.normalize_production(await self.row(ProductionBatch, 'production_batch_id', identifier))
        result['items'] = [dict(r) for r in (await self.db.execute(select(ProductionItem.__table__).where(
            *self.visible(ProductionItem), ProductionItem.production_batch_id == identifier
        ).order_by(ProductionItem.production_item_id))).mappings()]
        return result

    async def get(self, identifier):
        await require_permission(self.db, self.scope, 'Production.Read')
        await self.row(ProductionBatch, 'production_batch_id', identifier, lock=True)
        return await self.detail(identifier)

    async def list(self, *, offset=0, limit=20, kitchen=None, menu=None, status=None):
        await require_permission(self.db, self.scope, 'Production.Read')
        query = select(ProductionBatch.__table__).where(*self.visible(ProductionBatch))
        for key, value in (('kitchen', kitchen), ('menu', menu), ('status', status)):
            if value is not None:
                query = query.where(getattr(ProductionBatch, key) == value)
        rows = (await self.db.execute(query.order_by(ProductionBatch.created_at.desc(), ProductionBatch.production_batch_id.desc())
            .offset(offset).limit(limit + 1))).mappings().all()
        return {'items': [self.normalize_production(r) for r in rows[:limit]], 'offset': offset, 'limit': limit,
                'next_offset': offset + limit if len(rows) > limit else None}

    async def create(self, payload):
        await require_permission(self.db, self.scope, 'Production.Write')
        await self.active(Kitchen, 'kitchen_id', payload.kitchen)
        food = await self.active(FoodItem, 'food_item_id', payload.menu)
        # Food lock serializes recipe inserts/updates; shared recipe locks also cover deletes.
        recipes = (await self.db.execute(select(Recipe.__table__).where(*self.visible(Recipe),
            Recipe.food_item_id == payload.menu).order_by(Recipe.raw_material_id).with_for_update(read=True))).mappings().all()
        if not 1 <= len(recipes) <= 100:
            raise ProductionConflictError('Production requires 1..100 recipe lines')
        snapshot = {'schema_version': 1, 'food_version': food['version'], 'food_category': food['category'],
                    'holding_limit_minutes': food['holding_limit_minutes'], 'uom': food['uom'], 'items': []}
        for recipe in recipes:
            material = await self.active(RawMaterial, 'raw_material_id', recipe['raw_material_id'])
            if recipe['uom'] != material['uom'] or not recipe['quantity'].is_finite() or recipe['quantity'] <= 0:
                raise ProductionConflictError('Recipe quantity and material unit must be valid')
            required = (recipe['quantity'] * payload.planned_quantity).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)
            if not 0 < required <= Decimal('99999999.999999'):
                raise ProductionConflictError('Recipe requirement outside supported quantity precision')
            snapshot['items'].append({k: recipe[k] for k in ('recipe_id', 'version', 'raw_material_id', 'quantity', 'uom')} | {'required_quantity': required})
        snapshot = RecipeSnapshot.model_validate(snapshot).model_dump(mode='json')
        identifier = uuid4()
        await self.db.execute(insert(ProductionBatch).values(production_batch_id=identifier,
            **payload.model_dump(), recipe_snapshot=snapshot, status='CREATED', **self.audit))
        await sync_source(self.db, self.scope, 'PRODUCTION_BATCH', identifier)
        result = await self.detail(identifier)
        await self.event('production.created', result)
        return result

    def check(self, row, version, status):
        if row['version'] != version:
            raise VersionConflictError()
        if row['status'] != status:
            raise ProductionConflictError(f'Production must be {status}')
        if row['recipe_snapshot'] is None or row['planned_quantity'] is None:
            raise ProductionConflictError('Legacy production has no executable recipe snapshot')

    async def start(self, identifier, payload):
        await require_permission(self.db, self.scope, 'Production.Start')
        initial = await self.row(ProductionBatch, 'production_batch_id', identifier)
        # Same parent order as putaway; material batches locked in UUID order.
        await self.active(Kitchen, 'kitchen_id', initial['kitchen'])
        storages = {}
        for sid in sorted({i.storage_id for i in payload.items}):
            storage = await self.active(Storage, 'storage_id', sid)
            if storage['kitchen_id'] != initial['kitchen']:
                raise ProductionConflictError('Stock storage must belong to production kitchen')
            storages[sid] = storage
        await self.active(FoodItem, 'food_item_id', initial['menu'])
        current = await self.row(ProductionBatch, 'production_batch_id', identifier, lock=True)
        self.check(current, payload.expected_version, 'CREATED')
        snapshot = RecipeSnapshot.model_validate(current['recipe_snapshot'])
        materials = {}
        for mid in sorted({i.raw_material_id for i in snapshot.items}):
            materials[mid] = await self.active(RawMaterial, 'raw_material_id', mid)
        checked, totals = [], {}
        now = datetime.now(UTC)
        for source in sorted(payload.items, key=lambda i: i.raw_material_batch_id):
            try:
                batch = await self.row(RawMaterialBatch, 'raw_material_batch_id', source.raw_material_batch_id, lock=True)
            except RecordNotFoundError:
                raise ProductionConflictError('Material batch unavailable in this tenant') from None
            if batch['version'] != source.expected_version:
                raise VersionConflictError()
            material = materials.get(batch['raw_material_id'])
            if material is None:
                raise ProductionConflictError('Material is not in recipe snapshot')
            receipt = await self.row(Receiving, 'receiving_id', batch['receiving_id'])
            item = await self.row(ReceivingItem, 'raw_material_batch_id', source.raw_material_batch_id)
            if (batch['status'] != 'ACCEPTED' or item['accepted'] is not True or receipt['status'] != 'COMPLETED'
                    or receipt['kitchen_id'] != current['kitchen']):
                raise ProductionConflictError('Accepted stock from production kitchen required')
            if batch['expired_date'] is not None and batch['expired_date'] < now.date():
                raise ProductionConflictError('Expired stock cannot be used (UTC date)')
            if material['storage_type'] not in (None, storages[source.storage_id]['storage_type']):
                raise ProductionConflictError('Storage type does not match material requirement')
            required_line = next(i for i in snapshot.items if i.raw_material_id == batch['raw_material_id'])
            if material['uom'] != required_line.uom or item['uom'] != required_line.uom:
                raise ProductionConflictError('Stock unit does not match recipe snapshot')
            putaway = await self.db.scalar(select(func.coalesce(func.sum(StockEntry.quantity), 0)).where(
                *self.visible(StockEntry), StockEntry.raw_material_batch_id == source.raw_material_batch_id,
                StockEntry.storage_id == source.storage_id))
            used = await self.db.scalar(select(func.coalesce(func.sum(ProductionItem.quantity), 0)).where(
                *self.visible(ProductionItem), ProductionItem.raw_material_batch_id == source.raw_material_batch_id,
                ProductionItem.storage_id == source.storage_id))
            manual_used = await self.db.scalar(select(func.coalesce(func.sum(StockIssue.quantity), 0)).where(
                *self.visible(StockIssue), StockIssue.raw_material_batch_id == source.raw_material_batch_id,
                StockIssue.storage_id == source.storage_id))
            if source.quantity > putaway - used - manual_used:
                raise ProductionConflictError('Insufficient available stock in selected storage')
            totals[batch['raw_material_id']] = totals.get(batch['raw_material_id'], Decimal(0)) + source.quantity
            checked.append((source, batch, item['uom']))
        if totals != {i.raw_material_id: i.required_quantity for i in snapshot.items}:
            raise ProductionConflictError('Material quantities must exactly match recipe snapshot requirements')
        # All checks precede any consumption. Caller rolls back all writes on any failure.
        production_asset = await sync_source(self.db, self.scope, 'PRODUCTION_BATCH', identifier)
        kitchen_asset = await sync_source(self.db, self.scope, 'KITCHEN', current['kitchen'])
        for source, batch, uom in checked:
            bid, iid = source.raw_material_batch_id, uuid4()
            await self.db.execute(update(RawMaterialBatch).where(*self.visible(RawMaterialBatch),
                RawMaterialBatch.raw_material_batch_id == bid).values(version=batch['version'] + 1,
                    updated_at=now, updated_by=self.scope.actor_id))
            await self.db.execute(insert(ProductionItem).values(production_item_id=iid,
                production_batch_id=identifier, raw_material_batch_id=bid, storage_id=source.storage_id,
                batch_version=batch['version'] + 1, quantity=source.quantity, uom=uom, **self.audit))
            asset = await sync_source(self.db, self.scope, 'RAW_MATERIAL_BATCH', bid)
            location = await sync_source(self.db, self.scope, 'STORAGE', source.storage_id)
            await self.db.execute(insert(AssetRelationship).values(relationship_uuid=uuid4(),
                parent_uuid=asset['asset_uuid'], child_uuid=production_asset['asset_uuid'], relationship_type='USED', **self.audit))
            await self.db.execute(insert(AssetMovement).values(movement_id=uuid4(), asset_type='RAW_MATERIAL_BATCH',
                asset_uuid=asset['asset_uuid'], movement_type='ISSUE', from_location=location['asset_uuid'],
                to_location=kitchen_asset['asset_uuid'], operator=self.scope.actor_id, movement_time=now,
                remarks=str(iid), **self.audit))
        await self.db.execute(update(ProductionBatch).where(*self.visible(ProductionBatch),
            ProductionBatch.production_batch_id == identifier).values(status='RUNNING', started_at=now,
                updated_at=now, updated_by=self.scope.actor_id, version=current['version'] + 1))
        await sync_source(self.db, self.scope, 'PRODUCTION_BATCH', identifier)
        result = await self.detail(identifier)
        await self.event('production.started', result)
        return result

    async def finish(self, identifier, payload, cancel=False):
        await require_permission(self.db, self.scope, 'Production.Cancel' if cancel else 'Production.Complete')
        current = await self.row(ProductionBatch, 'production_batch_id', identifier, lock=True)
        self.check(current, payload.expected_version, 'CREATED' if cancel else 'RUNNING')
        now = datetime.now(UTC)
        values = {'status': 'CANCELLED' if cancel else 'COMPLETED', 'version': current['version'] + 1,
                  'updated_at': now, 'updated_by': self.scope.actor_id}
        if not cancel:
            if payload.actual_quantity > current['planned_quantity']:
                raise ProductionConflictError('Actual quantity cannot exceed planned quantity')
            values.update(actual_quantity=payload.actual_quantity,
                          initial_temperature=payload.initial_temperature, finished_at=now)
        await self.db.execute(update(ProductionBatch).where(*self.visible(ProductionBatch),
            ProductionBatch.production_batch_id == identifier).values(**values))
        if not cancel and payload.food_sensor_device_uuid is not None:
            device = (await self.db.execute(select(Device.__table__).where(
                Device.tenant_id == self.scope.tenant_id,
                Device.device_uuid == payload.food_sensor_device_uuid,
                Device.deleted_at.is_(None), Device.status == 'ACTIVE',
                Device.device_type.in_(['FOOD_TEMPERATURE', 'TEMPERATURE', 'FOOD_SENSOR']),
            ).with_for_update(read=True))).mappings().one_or_none()
            if device is None:
                raise ProductionConflictError('Active food temperature device required')
            await self.db.execute(insert(FoodSensorBinding).values(
                binding_id=uuid4(), tenant_id=self.scope.tenant_id,
                device_uuid=payload.food_sensor_device_uuid, production_batch_id=identifier,
                package_id=None, phase='PRODUCTION', started_at=now, **self.audit,
            ))
        await sync_source(self.db, self.scope, 'PRODUCTION_BATCH', identifier)
        if not cancel:
            location = await self.db.scalar(select(DigitalAsset.asset_uuid).where(*self.visible(DigitalAsset),
                DigitalAsset.asset_type == 'KITCHEN', DigitalAsset.entity_uuid == current['kitchen']))
            if location is None:
                raise ProductionConflictError('Production kitchen registry unavailable')
            asset = await self.db.scalar(select(DigitalAsset.asset_uuid).where(*self.visible(DigitalAsset),
                DigitalAsset.asset_type == 'PRODUCTION_BATCH', DigitalAsset.entity_uuid == identifier))
            await self.db.execute(insert(AssetMovement).values(movement_id=uuid4(), asset_type='PRODUCTION_BATCH',
                asset_uuid=asset, movement_type='PRODUCTION', from_location=None, to_location=location,
                operator=self.scope.actor_id, movement_time=now, remarks=None, **self.audit))
        result = await self.detail(identifier)
        await self.event('production.cancelled'  if cancel else 'production.completed', result)
        return result

    async def event(self, event_type, detail):
        await self.db.execute(insert(EventLog).values(event_uuid=uuid4(), event_type=event_type,
            entity_type='PRODUCTION_BATCH', entity_uuid=detail['production_batch_id'],
            payload={'schema_version': 1, 'actor_id': str(self.scope.actor_id),
                     'production': ProductionDetail.model_validate(detail).model_dump(mode='json')}, **self.audit))
