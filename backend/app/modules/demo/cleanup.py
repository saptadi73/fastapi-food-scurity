from uuid import UUID

from sqlalchemy import delete, or_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events.orm import EventLog
from app.modules.complaint.infrastructure.orm import Complaint
from app.modules.consumption.infrastructure.orm import Consumption
from app.modules.fleet.infrastructure.orm import Delivery, DeliveryItem, SchoolReceiving
from app.modules.production.infrastructure.orm import Package, ProductionBatch, ProductionItem
from app.modules.receiving.infrastructure.orm import RawMaterialBatch, Receiving, ReceivingItem, StockEntry, StockIssue
from app.modules.recall.infrastructure.orm import Recall, RecallWithdrawal
from app.modules.signature.infrastructure import SignatureEvidence
from app.modules.telemetry.infrastructure.orm import FoodSensorBinding, HoldingLog, TemperatureLog
from app.modules.traceability.infrastructure.orm import AssetMovement, AssetRelationship, DigitalAsset

DEFAULT_TENANT_CODE = 'FSOS_EXPO'
TRANSACTIONAL_ASSET_TYPES = ('RECEIVING', 'RAW_MATERIAL_BATCH', 'PRODUCTION_BATCH', 'PACKAGE', 'DELIVERY',
                             'COMPLAINT', 'RECALL', 'CONSUMPTION')
TRANSACTIONAL_MODELS = (
    Consumption, SchoolReceiving, DeliveryItem, Delivery, RecallWithdrawal, Recall, Complaint,
    HoldingLog, FoodSensorBinding,
    Package, ProductionItem, ProductionBatch, StockIssue, StockEntry, ReceivingItem, RawMaterialBatch, Receiving,
    AssetMovement, AssetRelationship,
)
# Append-only evidence tables whose row-level DELETE guards are suspended only inside the reset transaction.
GUARDED_TABLES = ('consumption', 'school_receiving', 'delivery_item', 'recall_withdrawal', 'holding_log',
                  'production_item', 'stock_issue', 'stock_entry', 'asset_movement', 'event_log',
                  'temperature_log', 'signature_evidence')
DELETE_GUARDS = text("""
    SELECT c.oid::regclass::text AS relation, t.tgname
    FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid
    WHERE NOT t.tgisinternal AND t.tgenabled <> 'D' AND (t.tgtype & 8) <> 0
      AND (c.oid IN (SELECT to_regclass('public.' || name) FROM unnest(CAST(:tables AS text[])) AS name)
           OR c.oid IN (SELECT i.inhrelid FROM pg_inherits i
                        WHERE i.inhparent IN (SELECT to_regclass('public.' || name)
                                              FROM unnest(CAST(:tables AS text[])) AS name)))
""")


async def _set_guards(session: AsyncSession, guards, action: str) -> None:
    quote = session.bind.dialect.identifier_preparer.quote
    for relation, trigger in guards:
        await session.execute(text(f'ALTER TABLE {relation} {action} TRIGGER {quote(trigger)}'))


async def cleanup(session: AsyncSession, tenant_id: UUID) -> dict[str, int]:
    """Must run inside a transaction on the owner/admin connection; guards revert on commit or rollback."""
    guards = (await session.execute(DELETE_GUARDS, {'tables': list(GUARDED_TABLES)})).all()
    await _set_guards(session, guards, 'DISABLE')
    removed: dict[str, int] = {}
    result = await session.execute(delete(SignatureEvidence.__table__).where(
        SignatureEvidence.tenant_id == tenant_id,
        SignatureEvidence.entity_type.in_(('SCHOOL_RECEIVING', 'COMPLAINT'))))
    removed['signature_evidence'] = result.rowcount or 0
    result = await session.execute(delete(TemperatureLog.__table__).where(
        TemperatureLog.tenant_id == tenant_id,
        or_(TemperatureLog.package_uuid.is_not(None), TemperatureLog.production_batch_uuid.is_not(None))))
    removed['temperature_log'] = result.rowcount or 0
    for model in TRANSACTIONAL_MODELS:
        result = await session.execute(delete(model.__table__).where(model.tenant_id == tenant_id))
        removed[model.__tablename__] = result.rowcount or 0
    result = await session.execute(delete(DigitalAsset.__table__).where(
        DigitalAsset.tenant_id == tenant_id, DigitalAsset.asset_type.in_(TRANSACTIONAL_ASSET_TYPES)))
    removed['digital_asset'] = result.rowcount or 0
    result = await session.execute(delete(EventLog.__table__).where(
        EventLog.tenant_id == tenant_id, EventLog.entity_type.in_(TRANSACTIONAL_ASSET_TYPES)))
    removed['event_log'] = result.rowcount or 0
    await _set_guards(session, guards, 'ENABLE')
    return removed
