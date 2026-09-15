from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, insert, or_, select, update

from app.core.database.scope import RecordNotFoundError, VersionConflictError
from app.core.events.orm import EventLog
from app.modules.authentication.infrastructure.authorization import require_permission
from app.modules.master.infrastructure.orm import Kitchen, RawMaterial, Supplier, SupplierMaterial
from app.modules.receiving.infrastructure.orm import RawMaterialBatch, Receiving, ReceivingItem
from app.modules.receiving.schemas.receiving import ReceivingDetail
from app.modules.traceability.infrastructure.orm import (
    AssetMovement,
    AssetRelationship,
    DigitalAsset,
)
from app.modules.traceability.infrastructure.registry import sync_source


class ReceivingConflictError(Exception):
    pass


class ReceivingService:
    """The authenticated dependency owns the transaction, including event/registry writes."""

    def __init__(self, db, scope):
        self.db, self.scope = db, scope

    def visible(self, model):
        return model.tenant_id == self.scope.tenant_id, model.deleted_at.is_(None)

    @property
    def audit(self):
        return {'tenant_id': self.scope.tenant_id, 'created_by': self.scope.actor_id,
                'updated_by': self.scope.actor_id, 'version': 1}

    async def row(self, model, key, identifier, lock=False):
        query = select(model.__table__).where(*self.visible(model), getattr(model, key) == identifier)
        if lock:
            query = query.with_for_update()
        row = (await self.db.execute(query)).mappings().one_or_none()
        if row is None:
            raise RecordNotFoundError()
        return dict(row)

    async def detail(self, identifier):
        result = await self.row(Receiving, 'receiving_id', identifier)
        # Header lock held by caller keeps items and batches consistent.
        items = (await self.db.execute(select(ReceivingItem.__table__).where(
            *self.visible(ReceivingItem), ReceivingItem.receiving_id == identifier
        ).order_by(ReceivingItem.receiving_item_id))).mappings().all()
        batches = (await self.db.execute(select(RawMaterialBatch.__table__).where(
            *self.visible(RawMaterialBatch), RawMaterialBatch.receiving_id == identifier
        ))).mappings().all()
        by_id = {b['raw_material_batch_id']: dict(b) for b in batches}
        result['items'] = [dict(i, batch=by_id[i['raw_material_batch_id']]) for i in items]
        return result

    async def get(self, identifier, batch=False):
        await require_permission(self.db, self.scope, 'RawMaterialBatch.Read' if batch else 'Receiving.Read')
        if batch:
            return await self.row(RawMaterialBatch, 'raw_material_batch_id', identifier)
        # Serialize with completion to avoid a CREATED header with finalized items.
        await self.row(Receiving, 'receiving_id', identifier, lock=True)
        return await self.detail(identifier)

    async def list(self, *, batch=False, offset=0, limit=20, search=None, material_category=None,
                   sort='CREATED_DESC', **filters):
        await require_permission(self.db, self.scope, 'RawMaterialBatch.Read' if batch else 'Receiving.Read')
        model, key = (RawMaterialBatch, 'raw_material_batch_id') if batch else (Receiving, 'receiving_id')
        query = select(model.__table__).where(*self.visible(model))
        if batch:
            query = query.join(RawMaterial, (RawMaterial.tenant_id == RawMaterialBatch.tenant_id)
                               & (RawMaterial.raw_material_id == RawMaterialBatch.raw_material_id))
            query = query.join(Receiving, (Receiving.tenant_id == RawMaterialBatch.tenant_id)
                               & (Receiving.receiving_id == RawMaterialBatch.receiving_id))
            if material_category is not None:
                query = query.where(RawMaterial.category == material_category)
            if search is not None:
                term = f"%{search.strip().lower()}%"
                query = query.where(or_(
                    func.lower(RawMaterial.material_code).like(term),
                    func.lower(RawMaterial.material_name).like(term),
                    func.lower(RawMaterialBatch.batch_code).like(term),
                ))
        for field, value in filters.items():
            if value is not None:
                query = query.where(getattr(model, field) == value)
        if batch and sort == 'FEFO':
            ordering = (RawMaterialBatch.expired_date.is_(None), RawMaterialBatch.expired_date.asc(),
                        Receiving.received_at.asc(), RawMaterialBatch.created_at.asc(),
                        RawMaterialBatch.raw_material_batch_id.asc())
        elif batch and sort == 'FIFO':
            ordering = (Receiving.received_at.asc(), RawMaterialBatch.created_at.asc(),
                        RawMaterialBatch.raw_material_batch_id.asc())
        else:
            ordering = (model.created_at.desc(), getattr(model, key).desc())
        rows = (await self.db.execute(query.order_by(*ordering).offset(offset).limit(limit + 1))).mappings().all()
        return {'items': [dict(r) for r in rows[:limit]], 'offset': offset, 'limit': limit,
                'next_offset': offset + limit if len(rows) > limit else None}

    async def create(self, payload):
        await require_permission(self.db, self.scope, 'Receiving.Write')
        # Parent-before-child order shared with master writers; source sync needs write locks.
        for model, key, identifier, asset_type in (
            (Supplier, 'supplier_id', payload.supplier_id, 'SUPPLIER'),
            (Kitchen, 'kitchen_id', payload.kitchen_id, 'KITCHEN'),
        ):
            try:
                parent = await self.row(model, key, identifier, lock=True)
            except RecordNotFoundError:
                raise ReceivingConflictError('Active supplier, kitchen and material in this tenant required') from None
            if parent['status'] != 'ACTIVE':
                raise ReceivingConflictError('Active supplier, kitchen and material in this tenant required')
            await sync_source(self.db, self.scope, asset_type, identifier)
        materials = {}
        for identifier in sorted({i.raw_material_id for i in payload.items}):
            try:
                material = await self.row(RawMaterial, 'raw_material_id', identifier, lock=True)
            except RecordNotFoundError:
                raise ReceivingConflictError('Active supplier, kitchen and material in this tenant required') from None
            if material['status'] != 'ACTIVE':
                raise ReceivingConflictError('Active supplier, kitchen and material in this tenant required')
            link = await self.db.scalar(select(SupplierMaterial.supplier_material_id).where(
                *self.visible(SupplierMaterial), SupplierMaterial.supplier_id == payload.supplier_id,
                SupplierMaterial.raw_material_id == identifier).with_for_update(read=True))
            if link is None:
                raise ReceivingConflictError('Supplier-material link required')
            materials[identifier] = material
        identifier = uuid4()
        await self.db.execute(insert(Receiving.__table__).values(
            receiving_id=identifier, supplier_id=payload.supplier_id, kitchen_id=payload.kitchen_id,
            operator=self.scope.actor_id, received_at=payload.received_at, status='CREATED', **self.audit))
        await sync_source(self.db, self.scope, 'RECEIVING', identifier)
        for item in payload.items:
            batch_id = uuid4()
            await self.db.execute(insert(RawMaterialBatch.__table__).values(
                raw_material_batch_id=batch_id, receiving_id=identifier, supplier_id=payload.supplier_id,
                **item.model_dump(exclude={'quantity', 'temperature', 'condition', 'photo'}),
                status='CREATED', **self.audit))
            await self.db.execute(insert(ReceivingItem.__table__).values(
                receiving_item_id=uuid4(), receiving_id=identifier, raw_material_batch_id=batch_id,
                quantity=item.quantity, temperature=item.temperature, uom=materials[item.raw_material_id]['uom'],
                condition=item.condition, photo=item.photo, accepted=None, **self.audit))
            await sync_source(self.db, self.scope, 'RAW_MATERIAL_BATCH', batch_id)
        result = await self.detail(identifier)
        await self.event('receiving.created', result)
        return result

    async def asset_id(self, asset_type, entity_id):
        result = await self.db.scalar(select(DigitalAsset.asset_uuid).where(
            *self.visible(DigitalAsset), DigitalAsset.asset_type == asset_type, DigitalAsset.entity_uuid == entity_id))
        if result is None:
            raise ReceivingConflictError('Receiving source registry is incomplete')
        return result

    async def finalize(self, identifier, payload, *, cancel=False):
        await require_permission(self.db, self.scope, 'Receiving.Cancel' if cancel else 'Receiving.Complete')
        current = await self.row(Receiving, 'receiving_id', identifier, lock=True)
        if current['version'] != payload.expected_version:
            raise VersionConflictError()
        if current['status'] != 'CREATED':
            raise ReceivingConflictError('Only CREATED receiving can be completed or cancelled')
        detail = await self.detail(identifier)
        decisions = {} if cancel else {i.receiving_item_id: i.accepted for i in payload.items}
        if not cancel and set(decisions) != {i['receiving_item_id'] for i in detail['items']}:
            raise ReceivingConflictError('Decisions must include every receiving item exactly once')
        if not detail['items']:
            raise ReceivingConflictError('Receiving must contain items')
        now = datetime.now(UTC)
        for item in detail['items']:
            batch = item['batch']
            if batch['status'] != 'CREATED' or item['accepted'] is not None:
                raise ReceivingConflictError('Receiving items are already finalized')
            if decisions.get(item['receiving_item_id']) and batch['expired_date'] is not None and batch['expired_date'] < now.date():
                raise ReceivingConflictError('Expired batch cannot be accepted (UTC date)')
        status = 'CANCELLED' if cancel else 'COMPLETED'
        await self.db.execute(update(Receiving.__table__).where(*self.visible(Receiving), Receiving.receiving_id == identifier)
                              .values(status=status, version=Receiving.version + 1, updated_at=now, updated_by=self.scope.actor_id))
        receipt_asset = await sync_source(self.db, self.scope, 'RECEIVING', identifier)
        for item in detail['items']:
            accepted = None if cancel else decisions[item['receiving_item_id']]
            batch_id = item['raw_material_batch_id']
            batch_status = 'CANCELLED' if cancel else ('ACCEPTED' if accepted else 'REJECTED')
            await self.db.execute(update(ReceivingItem.__table__).where(*self.visible(ReceivingItem),
                ReceivingItem.receiving_item_id == item['receiving_item_id']).values(
                    accepted=accepted, version=ReceivingItem.version + 1, updated_at=now, updated_by=self.scope.actor_id))
            await self.db.execute(update(RawMaterialBatch.__table__).where(*self.visible(RawMaterialBatch),
                RawMaterialBatch.raw_material_batch_id == batch_id).values(
                    status=batch_status, version=RawMaterialBatch.version + 1, updated_at=now, updated_by=self.scope.actor_id))
            batch_asset = await sync_source(self.db, self.scope, 'RAW_MATERIAL_BATCH', batch_id)
            if accepted:
                supplier_asset = await self.asset_id('SUPPLIER', current['supplier_id'])
                kitchen_asset = await self.asset_id('KITCHEN', current['kitchen_id'])
                for parent, relationship in ((supplier_asset, 'SUPPLIED'), (receipt_asset['asset_uuid'], 'RECEIVED')):
                    await self.db.execute(insert(AssetRelationship.__table__).values(
                        relationship_uuid=uuid4(), parent_uuid=parent, child_uuid=batch_asset['asset_uuid'],
                        relationship_type=relationship, **self.audit))
                await self.db.execute(insert(AssetMovement.__table__).values(
                    movement_id=uuid4(), asset_type='RAW_MATERIAL_BATCH', asset_uuid=batch_asset['asset_uuid'],
                    movement_type='RECEIVING', from_location=None, to_location=kitchen_asset,
                    operator=self.scope.actor_id, movement_time=current['received_at'], remarks=None, **self.audit))
        result = await self.detail(identifier)
        await self.event('receiving.cancelled' if cancel else 'receiving.completed', result)
        return result

    async def event(self, event_type, detail):
        await self.db.execute(insert(EventLog.__table__).values(
            event_uuid=uuid4(), event_type=event_type, entity_type='RECEIVING', entity_uuid=detail['receiving_id'],
            payload={'schema_version': 1, 'actor_id': str(self.scope.actor_id),
                     'receiving': ReceivingDetail.model_validate(detail).model_dump(mode='json')}, **self.audit))
