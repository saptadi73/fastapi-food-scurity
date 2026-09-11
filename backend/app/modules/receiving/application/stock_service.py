from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, insert, select, update

from app.core.database.scope import RecordNotFoundError, VersionConflictError
from app.core.events.orm import EventLog
from app.modules.authentication.infrastructure.authorization import require_permission
from app.modules.master.infrastructure.orm import Kitchen, RawMaterial, Storage
from app.modules.production.infrastructure.orm import ProductionItem
from app.modules.receiving.application.service import ReceivingConflictError, ReceivingService
from app.modules.receiving.infrastructure.orm import (
    RawMaterialBatch,
    Receiving,
    ReceivingItem,
    StockEntry,
)
from app.modules.receiving.schemas.stock import StockEntryData
from app.modules.traceability.infrastructure.orm import AssetMovement
from app.modules.traceability.infrastructure.registry import sync_source


class StockService(ReceivingService):
    async def putaway(self, identifier, payload):
        await require_permission(self.db, self.scope, 'Stock.Putaway')
        # Follow master parent lock order before locking the transactional batch.
        batch = await self.row(RawMaterialBatch, 'raw_material_batch_id', identifier)
        receipt = await self.row(Receiving, 'receiving_id', batch['receiving_id'])
        try:
            kitchen = await self.row(Kitchen, 'kitchen_id', receipt['kitchen_id'], lock=True)
            storage = await self.row(Storage, 'storage_id', payload.storage_id, lock=True)
            material = await self.row(RawMaterial, 'raw_material_id', batch['raw_material_id'], lock=True)
        except RecordNotFoundError:
            raise ReceivingConflictError('Active kitchen, storage and material in this tenant required') from None
        if any(r['status'] != 'ACTIVE' for r in (kitchen, storage, material)):
            raise ReceivingConflictError('Active kitchen, storage and material required')
        if storage['kitchen_id'] != receipt['kitchen_id']:
            raise ReceivingConflictError('Storage must belong to receiving kitchen')
        if material['storage_type'] is not None and material['storage_type'] != storage['storage_type']:
            raise ReceivingConflictError('Storage type does not match material requirement')
        batch = await self.row(RawMaterialBatch, 'raw_material_batch_id', identifier, lock=True)
        if batch['version'] != payload.expected_version:
            raise VersionConflictError()
        now = datetime.now(UTC)
        if receipt['status'] != 'COMPLETED' or batch['status'] != 'ACCEPTED':
            raise ReceivingConflictError('Completed receiving and ACCEPTED batch required')
        if batch['expired_date'] is not None and batch['expired_date'] < now.date():
            raise ReceivingConflictError('Expired batch cannot be put away (UTC date)')
        item = await self.row(ReceivingItem, 'raw_material_batch_id', identifier)
        allocated = await self.db.scalar(select(func.coalesce(func.sum(StockEntry.quantity), 0)).where(
            *self.visible(StockEntry), StockEntry.raw_material_batch_id == identifier))
        if item['accepted'] is not True or payload.quantity > item['quantity'] - allocated:
            raise ReceivingConflictError('Quantity exceeds accepted unallocated stock')
        version = batch['version'] + 1
        await self.db.execute(update(RawMaterialBatch).where(*self.visible(RawMaterialBatch),
            RawMaterialBatch.raw_material_batch_id == identifier).values(
                version=version, updated_at=now, updated_by=self.scope.actor_id))
        entry = (await self.db.execute(insert(StockEntry.__table__).values(
            stock_entry_id=uuid4(), raw_material_batch_id=identifier, storage_id=payload.storage_id,
            quantity=payload.quantity, batch_version=version, **self.audit
        ).returning(StockEntry.__table__))).mappings().one()
        batch_asset = await sync_source(self.db, self.scope, 'RAW_MATERIAL_BATCH', identifier)
        storage_asset = await sync_source(self.db, self.scope, 'STORAGE', payload.storage_id)
        kitchen_asset = await sync_source(self.db, self.scope, 'KITCHEN', receipt['kitchen_id'])
        await self.db.execute(insert(AssetMovement.__table__).values(
            movement_id=uuid4(), asset_type='RAW_MATERIAL_BATCH', asset_uuid=batch_asset['asset_uuid'],
            movement_type='STORAGE', from_location=kitchen_asset['asset_uuid'],
            to_location=storage_asset['asset_uuid'], operator=self.scope.actor_id, movement_time=now,
            remarks=str(entry['stock_entry_id']), **self.audit))
        data = StockEntryData.model_validate(entry).model_dump(mode='json')
        await self.db.execute(insert(EventLog.__table__).values(
            event_uuid=uuid4(), event_type='stock.putaway', entity_type='RAW_MATERIAL_BATCH',
            entity_uuid=identifier, payload={'schema_version': 1, 'actor_id': str(self.scope.actor_id),
                                           'entry': data, 'uom': item['uom']}, **self.audit))
        return dict(entry)

    async def balance(self, identifier):
        await require_permission(self.db, self.scope, 'Stock.Read')
        batch = await self.row(RawMaterialBatch, 'raw_material_batch_id', identifier, lock=True)
        item = await self.row(ReceivingItem, 'raw_material_batch_id', identifier)
        receipt = await self.row(Receiving, 'receiving_id', batch['receiving_id'])
        kitchen = await self.row(Kitchen, 'kitchen_id', receipt['kitchen_id'])
        material = await self.row(RawMaterial, 'raw_material_id', batch['raw_material_id'])
        usable = (batch['status'] == 'ACCEPTED' and item['accepted'] is True
                  and receipt['status'] == 'COMPLETED' and kitchen['status'] == 'ACTIVE'
                  and material['status'] == 'ACTIVE'
                  and (batch['expired_date'] is None or batch['expired_date'] >= datetime.now(UTC).date()))
        rows = (await self.db.execute(select(StockEntry.storage_id, func.sum(StockEntry.quantity).label('quantity'),
                Storage.status, Storage.deleted_at, Storage.storage_type).join(Storage,
                (Storage.tenant_id == StockEntry.tenant_id) & (Storage.storage_id == StockEntry.storage_id))
            .where(*self.visible(StockEntry), StockEntry.raw_material_batch_id == identifier)
            .group_by(StockEntry.storage_id, Storage.status, Storage.deleted_at, Storage.storage_type)
            .order_by(StockEntry.storage_id))).mappings().all()
        issues = dict((await self.db.execute(select(ProductionItem.storage_id, func.sum(ProductionItem.quantity)).where(
            *self.visible(ProductionItem), ProductionItem.raw_material_batch_id == identifier,
            ProductionItem.storage_id.is_not(None)).group_by(ProductionItem.storage_id))).all())
        storages = [{'storage_id': r['storage_id'], 'quantity': r['quantity'],
                     'issued_quantity': issues.get(r['storage_id'], Decimal(0)),
                     'available_quantity': r['quantity'] - issues.get(r['storage_id'], Decimal(0)) if usable and r['status'] == 'ACTIVE'
                     and r['deleted_at'] is None and material['storage_type'] in (None, r['storage_type'])
                     else Decimal(0)} for r in rows]
        allocated = sum((r['quantity'] for r in storages), Decimal(0))
        accepted = item['quantity'] if item['accepted'] is True else Decimal(0)
        return {'raw_material_batch_id': identifier, 'version': batch['version'], 'uom': item['uom'],
                'accepted_quantity': accepted, 'putaway_quantity': allocated,
                'issued_quantity': sum(issues.values(), Decimal(0)),
                'unallocated_quantity': accepted - allocated,
                'available_quantity': sum((r['available_quantity'] for r in storages), Decimal(0)),
                'storages': storages}

    async def ledger(self, identifier, *, offset=0, limit=20):
        await require_permission(self.db, self.scope, 'Stock.Read')
        await self.row(RawMaterialBatch, 'raw_material_batch_id', identifier)
        rows = (await self.db.execute(select(StockEntry.__table__).where(
            *self.visible(StockEntry), StockEntry.raw_material_batch_id == identifier)
            .order_by(StockEntry.batch_version.desc()).offset(offset).limit(limit + 1))).mappings().all()
        return {'items': [dict(r) for r in rows[:limit]], 'offset': offset, 'limit': limit,
                'next_offset': offset + limit if len(rows) > limit else None}


    async def issues(self, identifier, *, offset=0, limit=20):
        await require_permission(self.db, self.scope, 'Stock.Read')
        await self.row(RawMaterialBatch, 'raw_material_batch_id', identifier)
        rows = (await self.db.execute(select(ProductionItem.__table__).where(
            *self.visible(ProductionItem), ProductionItem.raw_material_batch_id == identifier,
            ProductionItem.storage_id.is_not(None)).order_by(ProductionItem.batch_version.desc())
            .offset(offset).limit(limit + 1))).mappings().all()
        return {'items': [dict(r) for r in rows[:limit]], 'offset': offset, 'limit': limit,
                'next_offset': offset + limit if len(rows) > limit else None}
