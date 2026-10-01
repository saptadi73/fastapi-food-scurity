"""Seed a pre-built incident/traceability scenario for the exhibition tenant.

Builds directly on the masters created by `seed_exhibition_masters.py` (same
tenant/kitchen/suppliers/materials/schools/vehicle/menu). Additive and
idempotent like seed_demo_ready.py: never deletes or resets existing data, and
reruns produce zero new rows.

Unlike `demo_live_flow.py` (which is meant to be run live, step by step, in
front of an audience), this script is meant to be run once *before* the demo so
an incident/recall/traceability scenario already exists to click through:

  - One receiving of rice + chicken (same masters as the live flow), one
    production batch, four packages distributed to the four registered demo
    schools.
  - School 1: received GOOD, then an OPEN/HIGH contamination complaint is
    filed (bad smell). This activates same-production-batch package warnings.
  - School 2: received GOOD, no complaint (still shows up in the recall impact).
  - School 3: received GOOD and fully consumed (terminal; stays untouched by
    the recall so trainers can show the contrast).
  - School 4: delivery completed but the school has not filed a receiving yet
    (still in the field when the recall happens).
  - A recall is opened on the production batch, executed (marks the two
    still-open packages RECALLED) and one physical withdrawal is recorded.

Guard: only runs on development/testing, same as the other exhibition scripts.
"""
import argparse
import asyncio
import json
import sys
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid5

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config.settings import get_settings
from app.core.database.scope import ActorScope
from app.core.database.session import close_database, get_admin_engine
from app.modules.complaint.infrastructure.orm import Complaint
from app.modules.consumption.infrastructure.orm import Consumption
from app.modules.fleet.infrastructure.orm import Delivery, DeliveryItem, SchoolReceiving
from app.modules.master.infrastructure.orm import Kitchen
from app.modules.production.infrastructure.orm import Package, ProductionBatch, ProductionItem
from app.modules.recall.infrastructure.orm import Recall, RecallWithdrawal
from app.modules.receiving.infrastructure.orm import RawMaterialBatch, Receiving, ReceivingItem, StockEntry
from app.modules.traceability.infrastructure.orm import AssetMovement, AssetRelationship
from app.modules.traceability.infrastructure.registry import sync_source

# Same namespace as seed_exhibition_masters.py; tenant_code selects which exhibition
# tenant (and therefore which kitchen/suppliers/materials/schools/vehicle/menu) this
# scenario attaches to.
NS = UUID('c3f7e6d2-df3a-4d61-9b8b-0a2c8e7f5b31')
DEFAULT_TENANT_CODE = 'FSOS_EXPO'
BASE = datetime.now(UTC) - timedelta(hours=6)


def scoped(tenant_code: str, name: str) -> UUID:
    return uuid5(NS, f'{tenant_code}:{name}')


async def ensure(session, model, pk_name: str, pk: UUID, values: dict) -> bool:
    table = model.__table__
    existing = await session.scalar(select(table.c[pk_name]).where(table.c[pk_name] == pk))
    if existing is not None:
        return False
    await session.execute(insert(table).values(**{pk_name: pk}, **values))
    return True


async def required_master(session, model, pk_name: str, pk: UUID, label: str):
    row = await session.scalar(select(model.__table__).where(getattr(model, pk_name) == pk))
    if row is None:
        raise ValueError(f'{label} not found; run seed_exhibition_masters.py first (matching --tenant-code)')
    return row


async def seed(session, *, tenant_code: str) -> dict:
    TENANT = scoped(tenant_code, 'tenant')
    ACTOR = scoped(tenant_code, 'actor')

    def did(name: str) -> UUID:
        return scoped(tenant_code, name)

    def audit() -> dict:
        return {'tenant_id': TENANT, 'created_by': ACTOR, 'updated_by': ACTOR}

    async def sync(asset_type: str, entity_id: UUID) -> dict:
        return await sync_source(session, ActorScope(TENANT, ACTOR), asset_type, entity_id)

    created = 0
    reconciled = 0
    kitchen = did('kitchen:pusat')
    cold, dry = did('storage:cold'), did('storage:dry')
    zone_cold, zone_dry = did('zone:cold-a'), did('zone:dry-a')
    sup_tani, sup_ternak = did('supplier:tani'), did('supplier:ternak')
    rice, chicken = did('material:rice'), did('material:chicken')
    vehicle, driver = did('vehicle:box-01'), did('driver:andi')
    menu = did('food:menu-utama')
    pkg_type = did('packaging:lunchbox')
    schools = [did(f'school:{i}') for i in range(1, 5)]

    await required_master(session, Kitchen, 'kitchen_id', kitchen, 'Kitchen')

    incident = 'incident'
    receiving_id = did(f'{incident}:receiving:chicken')
    created += await ensure(session, Receiving, 'receiving_id', receiving_id, {
        'supplier_id': sup_ternak, 'kitchen_id': kitchen, 'operator': ACTOR,
        'received_at': BASE, 'status': 'COMPLETED', **audit()})
    receiving_rice_id = did(f'{incident}:receiving:rice')
    created += await ensure(session, Receiving, 'receiving_id', receiving_rice_id, {
        'supplier_id': sup_tani, 'kitchen_id': kitchen, 'operator': ACTOR,
        'received_at': BASE, 'status': 'COMPLETED', **audit()})

    batch_chicken = did(f'{incident}:batch:chicken')
    created += await ensure(session, RawMaterialBatch, 'raw_material_batch_id', batch_chicken, {
        'raw_material_id': chicken, 'receiving_id': receiving_id, 'supplier_id': sup_ternak,
        'batch_code': 'INCIDENT-AYAM-001', 'expired_date': date.today() + timedelta(days=2),
        'status': 'ACCEPTED', 'qr_code': 'QR-INCIDENT-AYAM-001', 'version': 3, **audit()})
    created += await ensure(session, ReceivingItem, 'receiving_item_id', did(f'{incident}:item:chicken'), {
        'receiving_id': receiving_id, 'raw_material_batch_id': batch_chicken, 'quantity': Decimal('60.000000'),
        'uom': 'kg', 'temperature': Decimal('4.10'), 'condition': 'GOOD', 'accepted': True, **audit()})
    created += await ensure(session, StockEntry, 'stock_entry_id', did(f'{incident}:stock:chicken'), {
        'raw_material_batch_id': batch_chicken, 'storage_id': cold, 'zone_id': zone_cold,
        'quantity': Decimal('60.000000'), 'batch_version': 2, **audit()})

    batch_rice = did(f'{incident}:batch:rice')
    created += await ensure(session, RawMaterialBatch, 'raw_material_batch_id', batch_rice, {
        'raw_material_id': rice, 'receiving_id': receiving_rice_id, 'supplier_id': sup_tani,
        'batch_code': 'INCIDENT-BERAS-001', 'expired_date': date.today() + timedelta(days=60),
        'status': 'ACCEPTED', 'qr_code': 'QR-INCIDENT-BERAS-001', 'version': 3, **audit()})
    created += await ensure(session, ReceivingItem, 'receiving_item_id', did(f'{incident}:item:rice'), {
        'receiving_id': receiving_rice_id, 'raw_material_batch_id': batch_rice, 'quantity': Decimal('120.000000'),
        'uom': 'kg', 'temperature': Decimal('27.00'), 'condition': 'GOOD', 'accepted': True, **audit()})
    created += await ensure(session, StockEntry, 'stock_entry_id', did(f'{incident}:stock:rice'), {
        'raw_material_batch_id': batch_rice, 'storage_id': dry, 'zone_id': zone_dry,
        'quantity': Decimal('120.000000'), 'batch_version': 2, **audit()})

    production_id = did(f'{incident}:production')
    finished_at = BASE + timedelta(hours=1)
    created += await ensure(session, ProductionBatch, 'production_batch_id', production_id, {
        'batch_code': 'MO-INCIDENT-001', 'kitchen': kitchen, 'menu': menu,
        'planned_quantity': Decimal('200.000000'), 'actual_quantity': Decimal('200.000000'),
        'initial_temperature': Decimal('74.00'),
        'holding_policy': {'schema_version': 1, 'rule_id': None, 'rule_version': None, 'food_category': 'HOT_MEAL',
                           'maximum_minutes': 120, 'warning_minutes': 90, 'discard_minutes': 150},
        'recipe_snapshot': {'schema_version': 1, 'food_version': 1, 'food_category': 'HOT_MEAL',
            'holding_limit_minutes': 120, 'uom': 'porsi', 'food_code': 'MENU-EXPO-UTAMA',
            'food_name': 'Nasi Ayam Sayur Expo', 'items': [
                {'recipe_id': str(did('recipe:utama:rice')), 'version': 1, 'raw_material_id': str(rice),
                 'quantity': '0.150000', 'required_quantity': '30.000000', 'uom': 'kg'},
                {'recipe_id': str(did('recipe:utama:chicken')), 'version': 1, 'raw_material_id': str(chicken),
                 'quantity': '0.080000', 'required_quantity': '16.000000', 'uom': 'kg'},
            ]},
        'started_at': BASE + timedelta(minutes=10), 'finished_at': finished_at,
        'holding_started_at': finished_at, 'holding_expired_at': finished_at + timedelta(minutes=120),
        'status': 'COMPLETED', **audit()})
    created += await ensure(session, ProductionItem, 'production_item_id', did(f'{incident}:pi:rice'), {
        'production_batch_id': production_id, 'raw_material_batch_id': batch_rice, 'storage_id': dry,
        'batch_version': 3, 'quantity': Decimal('30.000000'), 'uom': 'kg', **audit()})
    created += await ensure(session, ProductionItem, 'production_item_id', did(f'{incident}:pi:chicken'), {
        'production_batch_id': production_id, 'raw_material_batch_id': batch_chicken, 'storage_id': cold,
        'batch_version': 3, 'quantity': Decimal('16.000000'), 'uom': 'kg', **audit()})

    # Four packages from the same production batch, one per registered school.
    packages = {}
    for i, school in enumerate(schools, start=1):
        package_id = did(f'{incident}:package:{i}')
        created += await ensure(session, Package, 'package_id', package_id, {
            'package_code': f'PKG-INCIDENT-{i:03d}', 'production_batch_id': production_id,
            'package_type_id': pkg_type, 'package_number': i, 'quantity': Decimal('50.000000'),
            'initial_temperature': Decimal('68.00'), 'holding_started_at': finished_at,
            'holding_finished_at': finished_at + timedelta(minutes=5),
            'remaining_minutes': 90, 'expired_at': finished_at + timedelta(minutes=120),
            'status': 'DELIVERED', **audit(), 'version': 5})
        packages[i] = package_id

    delivery_id = did(f'{incident}:delivery')
    departure = finished_at + timedelta(minutes=15)
    created += await ensure(session, Delivery, 'delivery_id', delivery_id, {
        'vehicle': vehicle, 'driver': driver, 'kitchen_id': kitchen,
        'estimated_arrival_time': departure + timedelta(minutes=30), 'estimated_distance_km': Decimal('6.200'),
        'estimated_duration_minutes': 25, 'departure_time': departure,
        'arrival_time': departure + timedelta(minutes=28), 'status': 'COMPLETED', **audit(), 'version': 3})
    for i, school in enumerate(schools, start=1):
        created += await ensure(session, DeliveryItem, 'delivery_item_id', did(f'{incident}:di:{i}'), {
            'delivery_id': delivery_id, 'package_id': packages[i], 'school_id': school, **audit()})

    arrival = departure + timedelta(minutes=28)
    # School 1: received GOOD, later complained about.
    receipt_1 = did(f'{incident}:receipt:1')
    created += await ensure(session, SchoolReceiving, 'school_receiving_id', receipt_1, {
        'delivery_id': delivery_id, 'school': schools[0], 'package': packages[1],
        'received_time': arrival + timedelta(minutes=2), 'temperature': Decimal('57.00'), 'accepted': True,
        'expected_quantity': Decimal('50.000000'), 'received_quantity': Decimal('50.000000'), 'condition': 'GOOD',
        'notes': 'Diterima lengkap', 'uom': 'porsi', 'timer_status': 'SAFE', **audit()})
    # School 2: received GOOD, no complaint (still nonterminal -> reached by recall).
    receipt_2 = did(f'{incident}:receipt:2')
    created += await ensure(session, SchoolReceiving, 'school_receiving_id', receipt_2, {
        'delivery_id': delivery_id, 'school': schools[1], 'package': packages[2],
        'received_time': arrival + timedelta(minutes=3), 'temperature': Decimal('56.50'), 'accepted': True,
        'expected_quantity': Decimal('50.000000'), 'received_quantity': Decimal('50.000000'), 'condition': 'GOOD',
        'notes': 'Diterima lengkap', 'uom': 'porsi', 'timer_status': 'SAFE', **audit()})
    # School 3: received GOOD and fully consumed (terminal; untouched by recall).
    receipt_3 = did(f'{incident}:receipt:3')
    created += await ensure(session, SchoolReceiving, 'school_receiving_id', receipt_3, {
        'delivery_id': delivery_id, 'school': schools[2], 'package': packages[3],
        'received_time': arrival + timedelta(minutes=4), 'temperature': Decimal('55.00'), 'accepted': True,
        'expected_quantity': Decimal('50.000000'), 'received_quantity': Decimal('50.000000'), 'condition': 'GOOD',
        'notes': 'Diterima lengkap', 'uom': 'porsi', 'timer_status': 'SAFE', **audit()})
    created += await ensure(session, Consumption, 'consumption_id', did(f'{incident}:consumption:3'), {
        'package_id': packages[3], 'consumed_at': arrival + timedelta(minutes=20), 'remaining_minutes': 65,
        'safe': True, 'school_receiving_id': receipt_3, 'consumed_quantity': Decimal('50.000000'),
        'discarded_quantity': Decimal('0.000000'), 'notes': 'Dikonsumsi penuh', 'uom': 'porsi',
        'timer_status': 'SAFE', **audit()})
    # School 4: delivery completed, school has not filed a receiving yet.

    complaint_id = did(f'{incident}:complaint')
    complaint_created = await ensure(session, Complaint, 'complaint_id', complaint_id, {
        'package_id': packages[1], 'school_id': schools[0],
        'category': 'CONTAMINATION', 'severity': 'HIGH', 'status': 'OPEN',
        'description': 'Bau tidak sedap terdeteksi pada sampel sebelum dibagikan ke siswa.',
        'photo': None, 'reported_at': arrival + timedelta(minutes=30),
        **audit()})
    created += complaint_created
    if not complaint_created:
        complaint_row = (await session.execute(select(Complaint.__table__).where(
            Complaint.tenant_id == TENANT,
            Complaint.complaint_id == complaint_id,
        ))).mappings().one()
        desired_incident = {'category': 'CONTAMINATION', 'severity': 'HIGH', 'status': 'OPEN'}
        if any(complaint_row[field] != value for field, value in desired_incident.items()):
            await session.execute(update(Complaint.__table__).where(
                Complaint.tenant_id == TENANT,
                Complaint.complaint_id == complaint_id,
            ).values(**desired_incident, updated_at=datetime.now(UTC), updated_by=ACTOR))
            reconciled += 1

    recall_id = did(f'{incident}:recall')
    created += await ensure(session, Recall, 'recall_id', recall_id, {
        'production_batch_id': production_id,
        'reason': 'Laporan bau tidak sedap pada PKG-INCIDENT-001; menarik seluruh output MO-INCIDENT-001.',
        'started_at': arrival + timedelta(minutes=35), 'completed_at': None, 'version': 2, **audit()})
    # Execute effect modeled directly: nonterminal packages (1, 2, 4) become RECALLED; 3 stays CONSUMED, 1 was
    # already complained and also becomes RECALLED once execute runs (receiving decision GOOD is immutable evidence).
    for i in (1, 2, 4):
        current = (await session.execute(select(Package.__table__).where(
            Package.tenant_id == TENANT, Package.package_id == packages[i]))).mappings().one()
        if current['status'] not in {'CONSUMED', 'DISCARDED', 'REJECTED'}:
            await session.execute(update(Package.__table__).where(
                Package.tenant_id == TENANT, Package.package_id == packages[i],
            ).values(status='RECALLED', version=current['version'] + 1, updated_at=arrival + timedelta(minutes=40),
                     updated_by=ACTOR))
    created += await ensure(session, RecallWithdrawal, 'withdrawal_id', did(f'{incident}:withdrawal:1'), {
        'recall_id': recall_id, 'package_id': packages[1], 'evidence_code': 'WD-PKG-INCIDENT-001',
        'quantity': Decimal('50.000'), 'uom': 'porsi', 'condition_note': 'Sampel diamankan sekolah untuk pemeriksaan.',
        'photo': 'example/recall/withdrawal-pkg-incident-001.jpg', 'withdrawn_at': arrival + timedelta(minutes=45),
        'completed_at': arrival + timedelta(minutes=50), **audit()})

    for asset_type, entity in [
        ('RECEIVING', receiving_id), ('RECEIVING', receiving_rice_id),
        ('RAW_MATERIAL_BATCH', batch_chicken), ('RAW_MATERIAL_BATCH', batch_rice),
        ('PRODUCTION_BATCH', production_id), ('DELIVERY', delivery_id),
        *[('PACKAGE', packages[i]) for i in range(1, 5)],
    ]:
        await sync(asset_type, entity)
    production_asset = await sync('PRODUCTION_BATCH', production_id)
    package_assets = {i: await sync('PACKAGE', packages[i]) for i in range(1, 5)}
    school_assets = {i: await sync('SCHOOL', schools[i - 1]) for i in range(1, 5)}
    complaint_asset = await sync('COMPLAINT', complaint_id)
    recall_asset = await sync('RECALL', recall_id)

    for i in range(1, 5):
        created += await ensure(session, AssetRelationship, 'relationship_uuid', did(f'{incident}:rel:packaged:{i}'), {
            'parent_uuid': production_asset['asset_uuid'], 'child_uuid': package_assets[i]['asset_uuid'],
            'relationship_type': 'PACKAGED', **audit()})
        created += await ensure(session, AssetRelationship, 'relationship_uuid', did(f'{incident}:rel:delivered:{i}'), {
            'parent_uuid': package_assets[i]['asset_uuid'], 'child_uuid': school_assets[i]['asset_uuid'],
            'relationship_type': 'DELIVERED', **audit()})
        created += await ensure(session, AssetMovement, 'movement_id', did(f'{incident}:mv:delivered:{i}'), {
            'asset_type': 'PACKAGE', 'asset_uuid': package_assets[i]['asset_uuid'], 'movement_type': 'SCHOOL_RECEIVING',
            'from_location': None, 'to_location': school_assets[i]['asset_uuid'], 'operator': ACTOR,
            'movement_time': arrival, 'remarks': None, **audit()})
    created += await ensure(session, AssetRelationship, 'relationship_uuid', did(f'{incident}:rel:complaint'), {
        'parent_uuid': package_assets[1]['asset_uuid'], 'child_uuid': complaint_asset['asset_uuid'],
        'relationship_type': 'REPORTED', **audit()})
    created += await ensure(session, AssetRelationship, 'relationship_uuid', did(f'{incident}:rel:recall'), {
        'parent_uuid': production_asset['asset_uuid'], 'child_uuid': recall_asset['asset_uuid'],
        'relationship_type': 'RECALLED', **audit()})

    return {
        'tenant_id': str(TENANT), 'tenant_code': tenant_code,
        'created': int(created), 'reconciled': int(reconciled),
        'production_batch_code': 'MO-INCIDENT-001',
        'complaint_id': str(complaint_id), 'recall_id': str(recall_id),
        'incident': {'category': 'CONTAMINATION', 'severity': 'HIGH', 'status': 'OPEN'},
        'packages': {f'school_{i}': f'PKG-INCIDENT-{i:03d}' for i in range(1, 5)},
        'note': 'School 1/2/4 packages RECALLED, school 3 stays CONSUMED (terminal) after recall execute.',
        'demo_endpoints': {
            'package_alert': '/api/v1/complaints/package/{package_id}/alerts',
            'batch_impact': f'/api/v1/complaints/{complaint_id}/batch-impact',
            'complaint_photo': '/api/v1/uploads/complaint-photo',
            'complaint_signature': f'/api/v1/signatures/targets/complaint/{complaint_id}',
        },
        'traceability_hint': 'Open traceability passport/impact on the production batch or raw material batch '
                             'asset_uuid (from GET /production-batches/{id} or /raw-material-batches/{id}) to see '
                             'the fan-out across all four schools.',
    }


async def main():
    try:
        settings = get_settings()
        if settings.environment not in {'development', 'testing'}:
            raise ValueError('Exhibition incident seed requires ENVIRONMENT=development or testing')
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--tenant-code', default=DEFAULT_TENANT_CODE,
                            help='Tenant code whose masters this scenario attaches to; must match the '
                                 '--tenant-code used with seed_exhibition_masters.py')
        args = parser.parse_args()
        factory = async_sessionmaker(get_admin_engine())
        async with factory() as session, session.begin():
            result = await seed(session, tenant_code=args.tenant_code)
        print(json.dumps(result, default=str, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001 - keep secrets/URLs out of logs
        print(json.dumps({'error_type': type(exc).__name__, 'detail': str(exc),
                          'action': 'Run seed_exhibition_masters.py first; check ENVIRONMENT/ADMIN_DATABASE_URL.'}))
        return 1
    finally:
        await close_database()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
