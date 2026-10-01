"""Reset the exhibition demo tenant's transactional data so it can be re-run.

Hard-deletes only *transactional* rows (receiving, batches, stock ledger,
production, packages, delivery/manifest, school receiving, consumption,
complaint, recall/withdrawal, plus their traceability registry/movement/event
rows) for one tenant. Master data (tenant/login, kitchen, storage, supplier,
raw material, school, vehicle, driver, packaging type, menu/recipe) is left
untouched, so `demo_live_flow.py` and `seed_exhibition_incident.py` can be run
again immediately after.

This is destructive and only intended for the dedicated exhibition demo tenant
between rehearsals. It requires an explicit --confirm flag and only permits the
dedicated FSOS_EXPO tenant, so it can be used without changing ENVIRONMENT.
It never touches other tenants.
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID, uuid5

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.database.session import close_database, get_admin_engine
from app.core.events.orm import EventLog
from app.modules.complaint.infrastructure.orm import Complaint
from app.modules.consumption.infrastructure.orm import Consumption
from app.modules.fleet.infrastructure.orm import Delivery, DeliveryItem, SchoolReceiving
from app.modules.master.infrastructure.orm import Tenant
from app.modules.production.infrastructure.orm import Package, ProductionBatch, ProductionItem
from app.modules.recall.infrastructure.orm import Recall, RecallWithdrawal
from app.modules.receiving.infrastructure.orm import RawMaterialBatch, Receiving, ReceivingItem, StockEntry, StockIssue
from app.modules.traceability.infrastructure.orm import AssetMovement, AssetRelationship, DigitalAsset

NS = UUID('c3f7e6d2-df3a-4d61-9b8b-0a2c8e7f5b31')
DEFAULT_TENANT_CODE = 'FSOS_EXPO'
TRANSACTIONAL_ASSET_TYPES = ('RECEIVING', 'RAW_MATERIAL_BATCH', 'PRODUCTION_BATCH', 'PACKAGE', 'DELIVERY',
                            'COMPLAINT', 'RECALL', 'CONSUMPTION')

# Child-to-parent order so foreign keys never block the delete.
TRANSACTIONAL_MODELS = (
    Consumption, SchoolReceiving, DeliveryItem, Delivery, RecallWithdrawal, Recall, Complaint,
    Package, ProductionItem, ProductionBatch, StockIssue, StockEntry, ReceivingItem, RawMaterialBatch, Receiving,
    AssetMovement, AssetRelationship,
)


async def cleanup(session, tenant_id: UUID) -> dict:
    removed = {}
    for model in TRANSACTIONAL_MODELS:
        result = await session.execute(delete(model.__table__).where(model.tenant_id == tenant_id))
        removed[model.__tablename__] = result.rowcount
    result = await session.execute(delete(DigitalAsset.__table__).where(
        DigitalAsset.tenant_id == tenant_id, DigitalAsset.asset_type.in_(TRANSACTIONAL_ASSET_TYPES)))
    removed['digital_asset'] = result.rowcount
    result = await session.execute(delete(EventLog.__table__).where(
        EventLog.tenant_id == tenant_id, EventLog.entity_type.in_(TRANSACTIONAL_ASSET_TYPES)))
    removed['event_log'] = result.rowcount
    return removed


async def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--tenant-code', default=DEFAULT_TENANT_CODE,
                        help='Tenant code to reset; defaults to the exhibition demo tenant only')
    parser.add_argument('--confirm', action='store_true', required=True,
                        help='Required acknowledgement that this hard-deletes transactional rows')
    args = parser.parse_args()
    try:
        if args.tenant_code != DEFAULT_TENANT_CODE:
            raise ValueError(
                f'demo_cleanup.py only permits the dedicated demo tenant {DEFAULT_TENANT_CODE}; '
                'refusing to reset another tenant')
        factory = async_sessionmaker(get_admin_engine())
        async with factory() as session, session.begin():
            tenant_id = await session.scalar(select(Tenant.tenant_id).where(
                Tenant.tenant_code == args.tenant_code, Tenant.deleted_at.is_(None)))
            if tenant_id is None:
                raise ValueError(f'Tenant {args.tenant_code} not found; nothing to reset')
            removed = await cleanup(session, tenant_id)
        print(json.dumps({'tenant_code': args.tenant_code, 'tenant_id': str(tenant_id), 'removed': removed}, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001 - keep secrets/URLs out of logs
        print(json.dumps({'error_type': type(exc).__name__, 'detail': str(exc)}))
        return 1
    finally:
        await close_database()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
