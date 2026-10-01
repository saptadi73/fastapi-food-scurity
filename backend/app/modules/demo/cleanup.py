from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events.orm import EventLog
from app.modules.complaint.infrastructure.orm import Complaint
from app.modules.consumption.infrastructure.orm import Consumption
from app.modules.fleet.infrastructure.orm import Delivery, DeliveryItem, SchoolReceiving
from app.modules.production.infrastructure.orm import Package, ProductionBatch, ProductionItem
from app.modules.receiving.infrastructure.orm import RawMaterialBatch, Receiving, ReceivingItem, StockEntry, StockIssue
from app.modules.recall.infrastructure.orm import Recall, RecallWithdrawal
from app.modules.traceability.infrastructure.orm import AssetMovement, AssetRelationship, DigitalAsset

DEFAULT_TENANT_CODE = 'FSOS_EXPO'
TRANSACTIONAL_ASSET_TYPES = ('RECEIVING', 'RAW_MATERIAL_BATCH', 'PRODUCTION_BATCH', 'PACKAGE', 'DELIVERY',
                             'COMPLAINT', 'RECALL', 'CONSUMPTION')
TRANSACTIONAL_MODELS = (
    Consumption, SchoolReceiving, DeliveryItem, Delivery, RecallWithdrawal, Recall, Complaint,
    Package, ProductionItem, ProductionBatch, StockIssue, StockEntry, ReceivingItem, RawMaterialBatch, Receiving,
    AssetMovement, AssetRelationship,
)


async def cleanup(session: AsyncSession, tenant_id: UUID) -> dict[str, int]:
    removed: dict[str, int] = {}
    for model in TRANSACTIONAL_MODELS:
        result = await session.execute(delete(model.__table__).where(model.tenant_id == tenant_id))
        removed[model.__tablename__] = result.rowcount or 0
    result = await session.execute(delete(DigitalAsset.__table__).where(
        DigitalAsset.tenant_id == tenant_id, DigitalAsset.asset_type.in_(TRANSACTIONAL_ASSET_TYPES)))
    removed['digital_asset'] = result.rowcount or 0
    result = await session.execute(delete(EventLog.__table__).where(
        EventLog.tenant_id == tenant_id, EventLog.entity_type.in_(TRANSACTIONAL_ASSET_TYPES)))
    removed['event_log'] = result.rowcount or 0
    return removed
