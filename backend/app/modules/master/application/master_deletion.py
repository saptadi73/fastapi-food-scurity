"""Soft deletion guards for operational master resources; no cascading."""
from datetime import UTC, datetime

from sqlalchemy import select, update

from app.modules.complaint.infrastructure.orm import Complaint
from app.modules.fleet.infrastructure.orm import Delivery, DeliveryItem, SchoolReceiving
from app.modules.master.infrastructure.orm import (
    Device,
    Recipe,
    School,
    Storage,
    StorageZone,
    SupplierMaterial,
    Vehicle,
)
from app.modules.production.infrastructure.orm import ProductionBatch
from app.modules.receiving.infrastructure.orm import RawMaterialBatch, Receiving
from app.modules.telemetry.infrastructure.orm import GPSLog, TemperatureLog
from app.modules.traceability.infrastructure.registry import sync_source

REFERENCES = {
    'driver': ((Vehicle, 'driver_id'), (Delivery, 'driver')),
    'vehicle': ((Delivery, 'vehicle'), (GPSLog, 'vehicle_uuid')),
    'school': ((DeliveryItem, 'school_id'), (SchoolReceiving, 'school'), (Complaint, 'school_id')),
    'kitchen': ((Storage, 'kitchen_id'), (School, 'kitchen_id'), (Receiving, 'kitchen_id'), (ProductionBatch, 'kitchen')),
    'storage': ((StorageZone, 'storage_id'), (TemperatureLog, 'storage_uuid')),
    'storage_zone': ((Device, 'zone_id'),),
    'supplier': ((SupplierMaterial, 'supplier_id'), (Receiving, 'supplier_id')),
    'raw_material': ((SupplierMaterial, 'raw_material_id'), (Recipe, 'raw_material_id'), (RawMaterialBatch, 'raw_material_id')),
    'supplier_material': (),
}
ASSETS = {'vehicle': 'VEHICLE', 'school': 'SCHOOL', 'kitchen': 'KITCHEN', 'storage': 'STORAGE', 'supplier': 'SUPPLIER', 'raw_material': 'RAW_MATERIAL'}


class MasterInUseError(Exception):
    pass


async def soft_delete_master(db, scope, table, key, current):
    """Caller authorizes Delete and locks visible parent/version before invoking."""
    identifier = current[key]
    for model, column in REFERENCES[table.name]:
        child = model.__table__
        used = await db.scalar(select(child.c[column]).where(
            child.c.tenant_id == scope.tenant_id, child.c[column] == identifier,
            child.c.deleted_at.is_(None),
        ).limit(1))
        if used is not None:
            raise MasterInUseError('Master record is still referenced')
    now = datetime.now(UTC)
    audit = (await db.execute(update(table).where(
        table.c.tenant_id == scope.tenant_id, table.c[key] == identifier,
        table.c.deleted_at.is_(None), table.c.version == current['version'],
    ).values(deleted_at=now, deleted_by=scope.actor_id, updated_at=now,
             updated_by=scope.actor_id, version=table.c.version + 1).returning(
        table.c.deleted_at, table.c.deleted_by, table.c.updated_at, table.c.updated_by, table.c.version,
    ))).mappings().one()
    if table.name in ASSETS:
        await sync_source(db, scope, ASSETS[table.name], identifier)
    return {**current, **dict(audit)}
