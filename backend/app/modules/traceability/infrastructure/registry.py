"""Explicit source adapters; source and registry changes share the caller transaction."""
from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import func, insert, literal, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.scope import ActorScope, RecordNotFoundError
from app.modules.complaint.infrastructure.orm import Complaint
from app.modules.consumption.infrastructure.orm import Consumption
from app.modules.fleet.infrastructure.orm import Delivery
from app.modules.master.infrastructure.orm import (
    Device,
    Kitchen,
    RawMaterial,
    School,
    Storage,
    Supplier,
    Vehicle,
)
from app.modules.production.infrastructure.orm import Package, ProductionBatch
from app.modules.recall.infrastructure.orm import Recall
from app.modules.receiving.infrastructure.orm import RawMaterialBatch, Receiving
from app.modules.traceability.infrastructure.orm import DigitalAsset


@dataclass(frozen=True)
class SourceAdapter:
    model: type
    key: str
    label: str | None = None


SOURCES = {
    'SUPPLIER': SourceAdapter(Supplier, 'supplier_id', 'supplier_name'),
    'KITCHEN': SourceAdapter(Kitchen, 'kitchen_id', 'kitchen_name'),
    'STORAGE': SourceAdapter(Storage, 'storage_id', 'storage_name'),
    'VEHICLE': SourceAdapter(Vehicle, 'vehicle_id', 'plate_number'),
    'SCHOOL': SourceAdapter(School, 'school_id', 'school_name'),
    'DEVICE': SourceAdapter(Device, 'device_id', 'device_name'),
    'RAW_MATERIAL': SourceAdapter(RawMaterial, 'raw_material_id', 'material_name'),
    'RAW_MATERIAL_BATCH': SourceAdapter(RawMaterialBatch, 'raw_material_batch_id', 'batch_code'),
    'PRODUCTION_BATCH': SourceAdapter(ProductionBatch, 'production_batch_id', 'batch_code'),
    'PACKAGE': SourceAdapter(Package, 'package_id', 'package_code'),
    'DELIVERY': SourceAdapter(Delivery, 'delivery_id'),
    'RECEIVING': SourceAdapter(Receiving, 'receiving_id'),
    'CONSUMPTION': SourceAdapter(Consumption, 'consumption_id'),
    'COMPLAINT': SourceAdapter(Complaint, 'complaint_id'),
    'RECALL': SourceAdapter(Recall, 'recall_id'),
}


def source_adapter(asset_type: str) -> SourceAdapter:
    if type(asset_type) is not str or asset_type not in SOURCES:
        raise ValueError('Unsupported asset type')
    return SOURCES[asset_type]


async def inspect_registry(session: AsyncSession, scope: ActorScope, asset_type: str,
                           *, after_id: UUID | None, limit: int) -> dict:
    """One statement snapshot of a registry page; caller authorizes the trusted scope."""
    adapter = source_adapter(asset_type)
    source, registry = adapter.model.__table__, DigitalAsset.__table__
    fields = {
        'name': source.c[adapter.label] if adapter.label else literal(None),
        'status': source.c.status if 'status' in source.c else literal('RECORDED'),
        'deleted_at': source.c.deleted_at, 'deleted_by': source.c.deleted_by,
    }
    query = select(
        registry, source.c[adapter.key].label('source_id'),
        *(value.label(f'source_{key}') for key, value in fields.items()),
    ).select_from(registry.outerjoin(source,
        (source.c.tenant_id == registry.c.tenant_id)
        & (source.c[adapter.key] == registry.c.entity_uuid),
    )).where(registry.c.tenant_id == scope.tenant_id, registry.c.asset_type == asset_type)
    if after_id is not None:
        query = query.where(registry.c.asset_uuid > after_id)
    rows = (await session.execute(query.order_by(registry.c.asset_uuid).limit(limit + 1))).mappings().all()
    items = []
    for row in rows[:limit]:
        missing = row['source_id'] is None
        expected = {key: row[f'source_{key}'] for key in fields}
        if not adapter.label:
            expected['name'] = f"{asset_type} {row['entity_uuid']}"
        changed = [] if missing else [key for key in fields if row[key] != expected[key]]
        items.append({
            'asset_uuid': row['asset_uuid'], 'entity_uuid': row['entity_uuid'],
            'version': row['version'],
            'state': 'SOURCE_MISSING' if missing else ('PROJECTION_MISMATCH' if changed else 'IN_SYNC'),
            'changed_fields': changed,
            'source_deleted': None if missing else row['source_deleted_at'] is not None,
        })
    last_id = items[-1]['asset_uuid'] if items else None
    return {
        'asset_type': asset_type, 'processed': len(items),
        'issue_count': sum(item['state'] != 'IN_SYNC' for item in items),
        'items': items, 'last_id': last_id,
        'next_cursor': last_id if len(rows) > limit else None,
    }


async def sync_source(session: AsyncSession, scope: ActorScope, asset_type: str, entity_id: UUID) -> dict:
    """Internal primitive: caller must authorize before using it (like direct SQL)."""
    adapter = source_adapter(asset_type)
    source = adapter.model.__table__
    # One writer per source entity, including concurrent first registration.
    row = (await session.execute(select(source).where(
        source.c.tenant_id == scope.tenant_id, source.c[adapter.key] == entity_id,
    ).with_for_update())).mappings().one_or_none()
    if row is None:
        raise RecordNotFoundError('Asset source not found')
    values = {
        'name': row[adapter.label] if adapter.label else f'{asset_type} {entity_id}',
        'status': row.get('status', 'RECORDED'),
        'deleted_at': row['deleted_at'], 'deleted_by': row['deleted_by'],
    }
    registry = DigitalAsset.__table__
    predicate = (registry.c.tenant_id == scope.tenant_id, registry.c.asset_type == asset_type,
                 registry.c.entity_uuid == entity_id)
    existing = (await session.execute(select(registry).where(*predicate).with_for_update())).mappings().one_or_none()
    if existing is None:
        result = await session.execute(insert(registry).values(
            **values, asset_uuid=uuid4(), tenant_id=scope.tenant_id, asset_type=asset_type,
            entity_uuid=entity_id, code=str(entity_id), created_by=scope.actor_id,
            updated_by=scope.actor_id, version=1,
        ).returning(registry))
    elif all(existing[key] == value for key, value in values.items()):
        return dict(existing)
    else:
        result = await session.execute(update(registry).where(*predicate).values(
            **values, updated_by=scope.actor_id, updated_at=func.clock_timestamp(),
            version=registry.c.version + 1,
        ).returning(registry))
    return dict(result.mappings().one())
