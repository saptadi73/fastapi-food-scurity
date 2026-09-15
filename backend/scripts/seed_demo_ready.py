"""Seed frontend-ready demo data for development/testing only.

This script is additive and idempotent. It never deletes or resets existing data.
Do not run it against production.
"""
import asyncio
import json
import sys
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid5

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import insert, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config.settings import get_settings
from app.core.database.location_permissions import LOCATION_PERMISSIONS
from app.core.database.receiving_permissions import RECEIVING_PERMISSIONS
from app.core.database.session import close_database, get_admin_engine
from app.core.database.supply_permissions import SUPPLY_PERMISSIONS
from app.core.events.orm import EventLog
from app.modules.authentication.infrastructure.orm import Permission, Role, RolePermission, User, UserRole
from app.modules.authentication.infrastructure.passwords import hash_password_async
from app.modules.complaint.infrastructure.orm import Complaint
from app.modules.consumption.infrastructure.orm import Consumption
from app.modules.fleet.infrastructure.orm import Delivery, DeliveryItem, SchoolReceiving
from app.modules.master.infrastructure.orm import (
    Device,
    DeviceBinding,
    Driver,
    FoodItem,
    Kitchen,
    PackagingType,
    RawMaterial,
    Recipe,
    School,
    Storage,
    StorageZone,
    Supplier,
    SupplierMaterial,
    Tenant,
    Vehicle,
)
from app.modules.notification.infrastructure.orm import NotificationOutbox
from app.modules.production.infrastructure.orm import Package, ProductionBatch, ProductionItem
from app.modules.recall.infrastructure.orm import Recall, RecallWithdrawal
from app.modules.receiving.infrastructure.orm import RawMaterialBatch, Receiving, ReceivingItem, StockEntry, StockIssue
from app.modules.telemetry.infrastructure.orm import AlarmLog, GPSLog, TemperatureLog
from app.modules.traceability.infrastructure.orm import AssetMovement, AssetRelationship
from app.modules.traceability.infrastructure.registry import sync_source
from app.core.database.scope import ActorScope


NS = UUID('936a0fd6-6b4e-4f54-8ac6-084f57d3f3e2')
TENANT = uuid5(NS, 'tenant')
ACTOR = uuid5(NS, 'actor')
ROLE = uuid5(NS, 'role:frontend-admin')
PASSWORD = 'DemoFrontend123!'
BASE = datetime(2026, 9, 15, 1, 0, tzinfo=UTC)


def did(name: str) -> UUID:
    return uuid5(NS, name)


def audit():
    return {'tenant_id': TENANT, 'created_by': ACTOR, 'updated_by': ACTOR}


async def ensure(session, model, pk_name: str, pk: UUID, values: dict) -> bool:
    table = model.__table__
    existing = await session.scalar(select(table.c[pk_name]).where(table.c[pk_name] == pk))
    if existing is not None:
        return False
    await session.execute(insert(table).values(**{pk_name: pk}, **values))
    return True


async def ensure_permission(session, code: str) -> UUID:
    row = (await session.execute(select(Permission.__table__).where(
        Permission.tenant_id == TENANT,
        Permission.permission_code == code,
    ))).mappings().one_or_none()
    if row is not None:
        return row['permission_id']
    pid = did(f'permission:{code}')
    await session.execute(insert(Permission.__table__).values(
        permission_id=pid,
        permission_code=code,
        description=f'Demo permission {code}',
        **audit(),
    ))
    return pid


async def ensure_grant(session, permission_id: UUID) -> bool:
    exists = await session.scalar(select(RolePermission.role_permission_id).where(
        RolePermission.tenant_id == TENANT,
        RolePermission.role_id == ROLE,
        RolePermission.permission_id == permission_id,
    ))
    if exists is not None:
        return False
    await session.execute(insert(RolePermission.__table__).values(
        role_permission_id=did(f'grant:{permission_id}'),
        role_id=ROLE,
        permission_id=permission_id,
        **audit(),
    ))
    return True


async def sync(session, asset_type: str, entity_id: UUID) -> dict:
    return await sync_source(session, ActorScope(TENANT, ACTOR), asset_type, entity_id)


async def seed(session) -> dict:
    await session.execute(text('SELECT pg_advisory_xact_lock(20260915, 32)'))
    await session.execute(text("SELECT public.fsos_create_telemetry_partitions('2026-09-01'::date, 3)"))
    created = 0

    created += await ensure(session, Tenant, 'tenant_id', TENANT, {
        'tenant_code': 'FSOS_DEMO',
        'tenant_name': 'FSOS Frontend Demo',
        'status': 'ACTIVE',
        'created_by': ACTOR,
        'updated_by': ACTOR,
    })
    password_hash = await hash_password_async(PASSWORD)
    created += await ensure(session, User, 'user_id', ACTOR, {
        'tenant_id': TENANT,
        'username': 'frontend-admin',
        'fullname': 'Frontend Demo Admin',
        'email': 'frontend-admin@example.invalid',
        'password_hash': password_hash,
        'status': 'ACTIVE',
        'created_by': ACTOR,
        'updated_by': ACTOR,
    })
    created += await ensure(session, Role, 'role_id', ROLE, {
        'tenant_id': TENANT,
        'role_code': 'FRONTEND_ADMIN',
        'role_name': 'Frontend Demo Admin',
        'created_by': ACTOR,
        'updated_by': ACTOR,
    })
    created += await ensure(session, UserRole, 'user_role_id', did('user-role:frontend-admin'), {
        'tenant_id': TENANT,
        'user_id': ACTOR,
        'role_id': ROLE,
        'created_by': ACTOR,
        'updated_by': ACTOR,
    })
    grant_count = 0
    for code in sorted(set(LOCATION_PERMISSIONS) | set(SUPPLY_PERMISSIONS) | set(RECEIVING_PERMISSIONS) | {
        'Alarm.Read', 'Alarm.Acknowledge', 'DeviceSession.Read', 'DeviceSession.Close',
        'HoldingRule.Read', 'HoldingRule.Write', 'AlarmRule.Read', 'AlarmRule.Write', 'AlarmRule.Activate',
    }):
        grant_count += await ensure_grant(session, await ensure_permission(session, code))

    kitchen = did('kitchen:central')
    cold = did('storage:cold')
    dry = did('storage:dry')
    zone_cold = did('zone:cold-a')
    zone_dry = did('zone:dry-a')
    temp_device = did('device:temp-storage')
    gps_device = did('device:gps-vehicle')
    vehicle_temp_device = did('device:temp-vehicle')
    supplier = did('supplier:utama')
    school = did('school:sd-01')
    driver = did('driver:andi')
    vehicle = did('vehicle:box-01')
    food = did('food:nasi-ayam')
    packaging_type = did('packaging:lunchbox')
    material_rice = did('material:rice')
    material_chicken = did('material:chicken')

    masters = [
        (Kitchen, 'kitchen_id', kitchen, {'kitchen_code': 'DKP-01', 'kitchen_name': 'Dapur Pusat Demo',
            'latitude': Decimal('-7.250445'), 'longitude': Decimal('112.768845'), 'address': 'Jl. Demo Pangan 1',
            'capacity': 5000, 'status': 'ACTIVE', **audit()}),
        (Storage, 'storage_id', cold, {'kitchen_id': kitchen, 'storage_code': 'COLD-01',
            'storage_name': 'Cold Room Demo', 'storage_type': 'COLD_STORAGE', 'temperature_min': Decimal('1.00'),
            'temperature_max': Decimal('5.00'), 'status': 'ACTIVE', **audit()}),
        (Storage, 'storage_id', dry, {'kitchen_id': kitchen, 'storage_code': 'DRY-01',
            'storage_name': 'Dry Storage Demo', 'storage_type': 'DRY_STORAGE', 'temperature_min': Decimal('20.00'),
            'temperature_max': Decimal('30.00'), 'status': 'ACTIVE', **audit()}),
        (StorageZone, 'zone_id', zone_cold, {'storage_id': cold, 'zone_code': 'COLD-A1', 'zone_name': 'Rak Chiller A1', **audit()}),
        (StorageZone, 'zone_id', zone_dry, {'storage_id': dry, 'zone_code': 'DRY-A1', 'zone_name': 'Rak Kering A1', **audit()}),
        (Device, 'device_id', temp_device, {'device_uuid': did('device-uuid:temp-storage'), 'zone_id': zone_cold,
            'device_name': 'Sensor Suhu Cold Room', 'device_type': 'TEMPERATURE', 'firmware': 'demo-1.0.0',
            'hardware': 'demo-temp-v1', 'mqtt_topic': 'fsos/demo/storage/cold-01/temperature', 'status': 'ACTIVE',
            'last_online': BASE + timedelta(minutes=118), **audit()}),
        (Device, 'device_id', gps_device, {'device_uuid': did('device-uuid:gps-vehicle'), 'zone_id': None,
            'device_name': 'GPS Armada Box 01', 'device_type': 'GPS', 'firmware': 'demo-1.0.0',
            'hardware': 'demo-gps-v1', 'mqtt_topic': 'fsos/demo/fleet/box-01/gps', 'status': 'ACTIVE',
            'last_online': BASE + timedelta(minutes=118), **audit()}),
        (Device, 'device_id', vehicle_temp_device, {'device_uuid': did('device-uuid:temp-vehicle'), 'zone_id': None,
            'device_name': 'Sensor Suhu Box 01', 'device_type': 'TEMPERATURE', 'firmware': 'demo-1.0.0',
            'hardware': 'demo-temp-v1', 'mqtt_topic': 'fsos/demo/fleet/box-01/temperature', 'status': 'ACTIVE',
            'last_online': BASE + timedelta(minutes=118), **audit()}),
        (Supplier, 'supplier_id', supplier, {'supplier_code': 'SUP-DEMO-01', 'supplier_name': 'Pemasok Segar Demo',
            'phone': '0800000000', 'email': 'supplier@example.invalid', 'status': 'ACTIVE', **audit()}),
        (RawMaterial, 'raw_material_id', material_rice, {'material_code': 'RM-BERAS', 'material_name': 'Beras Premium',
            'category': 'CARBOHYDRATE', 'uom': 'kg', 'storage_type': 'DRY_STORAGE',
            'recommended_temperature_min': Decimal('20.00'), 'recommended_temperature_max': Decimal('30.00'),
            'maximum_storage_hours': Decimal('720.00'), 'status': 'ACTIVE', **audit()}),
        (RawMaterial, 'raw_material_id', material_chicken, {'material_code': 'RM-AYAM', 'material_name': 'Ayam Fillet',
            'category': 'PROTEIN', 'uom': 'kg', 'storage_type': 'COLD_STORAGE',
            'recommended_temperature_min': Decimal('1.00'), 'recommended_temperature_max': Decimal('5.00'),
            'maximum_storage_hours': Decimal('48.00'), 'status': 'ACTIVE', **audit()}),
        (SupplierMaterial, 'supplier_material_id', did('supplier-material:rice'), {'supplier_id': supplier, 'raw_material_id': material_rice, **audit()}),
        (SupplierMaterial, 'supplier_material_id', did('supplier-material:chicken'), {'supplier_id': supplier, 'raw_material_id': material_chicken, **audit()}),
        (School, 'school_id', school, {'kitchen_id': kitchen, 'school_code': 'SCH-DEMO-01', 'school_name': 'SD Demo 01',
            'latitude': Decimal('-7.265000'), 'longitude': Decimal('112.745000'), 'address': 'Jl. Sekolah Demo 1',
            'student_count': 450, 'status': 'ACTIVE', **audit()}),
        (Driver, 'driver_id', driver, {'driver_code': 'DRV-ANDI', 'driver_name': 'Andi Demo', 'phone': '0811111111',
            'status': 'ACTIVE', **audit()}),
        (Vehicle, 'vehicle_id', vehicle, {'vehicle_code': 'VH-BOX-01', 'plate_number': 'L 9001 FS',
            'vehicle_type': 'INSULATED_BOX', 'capacity': Decimal('500.00'), 'gps_device': gps_device,
            'driver_id': driver, 'status': 'ACTIVE', **audit()}),
        (DeviceBinding, 'binding_id', did('binding:gps-box-01'), {'device_id': gps_device, 'vehicle_id': vehicle, **audit()}),
        (FoodItem, 'food_item_id', food, {'food_code': 'MENU-NASI-AYAM', 'food_name': 'Nasi Ayam Demo',
            'category': 'HOT_MEAL', 'uom': 'portion', 'holding_limit_minutes': 120, 'status': 'ACTIVE', **audit()}),
        (Recipe, 'recipe_id', did('recipe:rice'), {'food_item_id': food, 'raw_material_id': material_rice,
            'quantity': Decimal('0.120000'), 'uom': 'kg', **audit()}),
        (Recipe, 'recipe_id', did('recipe:chicken'), {'food_item_id': food, 'raw_material_id': material_chicken,
            'quantity': Decimal('0.080000'), 'uom': 'kg', **audit()}),
        (PackagingType, 'package_type_id', packaging_type, {'code': 'LUNCHBOX-750', 'name': 'Lunch Box 750ml',
            'material': 'Food grade paper', 'volume': Decimal('750.000'), **audit()}),
    ]
    for model, pk_name, pk, values in masters:
        created += await ensure(session, model, pk_name, pk, values)

    receiving = did('receiving:001')
    batch_rice = did('raw-batch:rice:001')
    batch_chicken = did('raw-batch:chicken:001')
    created += await ensure(session, Receiving, 'receiving_id', receiving, {
        'supplier_id': supplier, 'kitchen_id': kitchen, 'operator': ACTOR, 'received_at': BASE,
        'status': 'COMPLETED', **audit()})
    for batch, material, code, expiry, qty, temp, condition, photo in [
        (batch_rice, material_rice, 'RB-BERAS-001', date(2026, 10, 15), Decimal('80.000000'), Decimal('26.50'), 'GOOD', 'example/receiving/beras-001.jpg'),
        (batch_chicken, material_chicken, 'RB-AYAM-001', date(2026, 9, 17), Decimal('45.000000'), Decimal('3.20'), 'GOOD', 'example/receiving/ayam-001.jpg'),
    ]:
        created += await ensure(session, RawMaterialBatch, 'raw_material_batch_id', batch, {
            'raw_material_id': material, 'receiving_id': receiving, 'supplier_id': supplier, 'batch_code': code,
            'expired_date': expiry, 'status': 'ACCEPTED', 'qr_code': f'QR-{code}', **audit()})
        created += await ensure(session, ReceivingItem, 'receiving_item_id', did(f'receiving-item:{code}'), {
            'receiving_id': receiving, 'raw_material_batch_id': batch, 'quantity': qty, 'uom': 'kg',
            'temperature': temp, 'condition': condition, 'photo': photo, 'accepted': True, **audit()})

    created += await ensure(session, StockEntry, 'stock_entry_id', did('stock-entry:rice'), {
        'raw_material_batch_id': batch_rice, 'storage_id': dry, 'zone_id': zone_dry, 'quantity': Decimal('80.000000'),
        'batch_version': 2, **audit()})
    created += await ensure(session, StockEntry, 'stock_entry_id', did('stock-entry:chicken'), {
        'raw_material_batch_id': batch_chicken, 'storage_id': cold, 'zone_id': zone_cold, 'quantity': Decimal('45.000000'),
        'batch_version': 2, **audit()})
    created += await ensure(session, StockIssue, 'stock_issue_id', did('stock-issue:chicken-qc'), {
        'raw_material_batch_id': batch_chicken, 'storage_id': cold, 'zone_id': zone_cold, 'quantity': Decimal('1.000000'),
        'batch_version': 3, 'issued_at': BASE + timedelta(minutes=20), 'reason': 'QC sample',
        'reference_code': 'QC-AYAM-001', **audit()})

    production = did('production:mo-001')
    created += await ensure(session, ProductionBatch, 'production_batch_id', production, {
        'batch_code': 'MO-2026-0001', 'kitchen': kitchen, 'menu': food, 'planned_quantity': Decimal('300.000000'),
        'actual_quantity': Decimal('295.000000'), 'initial_temperature': Decimal('72.50'),
        'holding_policy': {'maximum_minutes': 120, 'warning_minutes': 90, 'discard_minutes': 150},
        'recipe_snapshot': {'food_code': 'MENU-NASI-AYAM', 'food_name': 'Nasi Ayam Demo', 'uom': 'portion'},
        'started_at': BASE + timedelta(minutes=30), 'finished_at': BASE + timedelta(minutes=90),
        'holding_started_at': BASE + timedelta(minutes=90), 'holding_expired_at': BASE + timedelta(minutes=210),
        'status': 'COMPLETED', **audit()})
    created += await ensure(session, ProductionItem, 'production_item_id', did('production-item:rice'), {
        'production_batch_id': production, 'raw_material_batch_id': batch_rice, 'storage_id': dry,
        'batch_version': 3, 'quantity': Decimal('36.000000'), 'uom': 'kg', **audit()})
    created += await ensure(session, ProductionItem, 'production_item_id', did('production-item:chicken'), {
        'production_batch_id': production, 'raw_material_batch_id': batch_chicken, 'storage_id': cold,
        'batch_version': 4, 'quantity': Decimal('24.000000'), 'uom': 'kg', **audit()})

    package = did('package:001')
    created += await ensure(session, Package, 'package_id', package, {
        'package_code': 'PKG-2026-0001', 'production_batch_id': production, 'package_type_id': packaging_type,
        'package_number': 1, 'quantity': Decimal('50.000000'), 'initial_temperature': Decimal('68.20'),
        'holding_started_at': BASE + timedelta(minutes=95), 'holding_finished_at': BASE + timedelta(minutes=105),
        'remaining_minutes': 105, 'expired_at': BASE + timedelta(minutes=210), 'status': 'RECEIVED', **audit()})
    delivery = did('delivery:001')
    created += await ensure(session, Delivery, 'delivery_id', delivery, {
        'vehicle': vehicle, 'driver': driver, 'kitchen_id': kitchen,
        'estimated_arrival_time': BASE + timedelta(minutes=145), 'estimated_distance_km': Decimal('4.850'),
        'estimated_duration_minutes': 20, 'departure_time': BASE + timedelta(minutes=120),
        'arrival_time': BASE + timedelta(minutes=148), 'status': 'COMPLETED', **audit()})
    created += await ensure(session, DeliveryItem, 'delivery_item_id', did('delivery-item:001'), {
        'delivery_id': delivery, 'package_id': package, 'school_id': school, **audit()})
    receipt = did('school-receiving:001')
    created += await ensure(session, SchoolReceiving, 'school_receiving_id', receipt, {
        'delivery_id': delivery, 'school': school, 'package': package, 'received_time': BASE + timedelta(minutes=150),
        'temperature': Decimal('58.30'), 'accepted': True, 'photo': 'example/school-receiving/pkg-2026-0001.jpg',
        'expected_quantity': Decimal('50.000000'), 'received_quantity': Decimal('50.000000'), 'condition': 'GOOD',
        'notes': 'Diterima lengkap', 'uom': 'portion', 'timer_status': 'SAFE', **audit()})
    created += await ensure(session, Consumption, 'consumption_id', did('consumption:001'), {
        'package_id': package, 'consumed_at': BASE + timedelta(minutes=180), 'remaining_minutes': 30,
        'safe': True, 'school_receiving_id': receipt, 'consumed_quantity': Decimal('48.000000'),
        'discarded_quantity': Decimal('2.000000'), 'notes': 'Sisa dua porsi tidak dibagikan', 'uom': 'portion',
        'timer_status': 'SAFE', **audit()})

    for i, (lat, lon, speed) in enumerate([
        ('-7.250445', '112.768845', '0.000'), ('-7.253000', '112.764000', '25.000'),
        ('-7.256000', '112.759000', '31.000'), ('-7.260000', '112.752000', '34.000'),
        ('-7.265000', '112.745000', '10.000'),
    ]):
        created += await ensure(session, GPSLog, 'gps_log_id', did(f'gps:{i}'), {
            'vehicle_uuid': vehicle, 'recorded_at': BASE + timedelta(minutes=120 + i * 6),
            'mqtt_message_id': None, 'latitude': Decimal(lat), 'longitude': Decimal(lon),
            'speed': Decimal(speed), 'heading': Decimal('245.000'), 'altitude': Decimal('5.000'),
            'hdop': Decimal('0.900'), 'satellite': 12, **audit()})
    for i, temp in enumerate(['3.200', '3.400', '7.600', '4.100', '3.700']):
        created += await ensure(session, TemperatureLog, 'temperature_log_id', did(f'temp:storage:{i}'), {
            'device_uuid': did('device-uuid:temp-storage'), 'storage_uuid': cold,
            'recorded_at': BASE + timedelta(minutes=90 + i * 5), 'mqtt_message_id': None,
            'temperature': Decimal(temp), 'unit': 'C', **audit()})
    for i, temp in enumerate(['62.000', '60.500', '55.000', '58.000']):
        created += await ensure(session, TemperatureLog, 'temperature_log_id', did(f'temp:vehicle:{i}'), {
            'device_uuid': did('device-uuid:temp-vehicle'), 'storage_uuid': None,
            'recorded_at': BASE + timedelta(minutes=122 + i * 6), 'mqtt_message_id': None,
            'temperature': Decimal(temp), 'unit': 'C', **audit()})
    created += await ensure(session, AlarmLog, 'alarm_id', did('alarm:storage-spike'), {
        'device_uuid': did('device-uuid:temp-storage'), 'recorded_at': BASE + timedelta(minutes=100),
        'mqtt_message_id': None, 'alarm_code': 'TEMP_HIGH_COLD_ROOM', 'severity': 'HIGH',
        'description': 'Cold room temperature spike above threshold during demo.', 'acknowledged': False, **audit()})

    for asset_type, entity in [
        ('KITCHEN', kitchen), ('STORAGE', cold), ('STORAGE', dry), ('DEVICE', temp_device), ('DEVICE', gps_device),
        ('SUPPLIER', supplier), ('RAW_MATERIAL', material_rice), ('RAW_MATERIAL', material_chicken),
        ('RAW_MATERIAL_BATCH', batch_rice), ('RAW_MATERIAL_BATCH', batch_chicken), ('PRODUCTION_BATCH', production),
        ('PACKAGE', package), ('DELIVERY', delivery), ('SCHOOL', school), ('VEHICLE', vehicle),
    ]:
        await sync(session, asset_type, entity)
    package_asset = await sync(session, 'PACKAGE', package)
    production_asset = await sync(session, 'PRODUCTION_BATCH', production)
    school_asset = await sync(session, 'SCHOOL', school)
    for rel_name, parent, child, rel_type in [
        ('rel:production-package', production_asset['asset_uuid'], package_asset['asset_uuid'], 'PACKAGED'),
        ('rel:package-school', package_asset['asset_uuid'], school_asset['asset_uuid'], 'DELIVERED'),
    ]:
        created += await ensure(session, AssetRelationship, 'relationship_uuid', did(rel_name), {
            'parent_uuid': parent, 'child_uuid': child, 'relationship_type': rel_type, **audit()})
    created += await ensure(session, AssetMovement, 'movement_id', did('movement:package-received'), {
        'asset_type': 'PACKAGE', 'asset_uuid': package_asset['asset_uuid'], 'movement_type': 'SCHOOL_RECEIVING',
        'from_location': None, 'to_location': school_asset['asset_uuid'], 'operator': ACTOR,
        'movement_time': BASE + timedelta(minutes=150), 'remarks': str(receipt), **audit()})

    complaint = did('complaint:001')
    created += await ensure(session, Complaint, 'complaint_id', complaint, {
        'package_id': package, 'school_id': school, 'description': 'Bau asam terdeteksi pada sampel sebelum konsumsi.',
        'photo': 'example/complaints/pkg-2026-0001.jpg', 'reported_at': BASE + timedelta(minutes=160), **audit()})
    complaint_asset = await sync(session, 'COMPLAINT', complaint)
    created += await ensure(session, AssetRelationship, 'relationship_uuid', did('rel:package-complaint'), {
        'parent_uuid': package_asset['asset_uuid'], 'child_uuid': complaint_asset['asset_uuid'],
        'relationship_type': 'REPORTED', **audit()})
    created += await ensure(session, AssetMovement, 'movement_id', did('movement:complaint'), {
        'asset_type': 'PACKAGE', 'asset_uuid': package_asset['asset_uuid'], 'movement_type': 'COMPLAINT',
        'from_location': school_asset['asset_uuid'], 'to_location': None, 'operator': ACTOR,
        'movement_time': BASE + timedelta(minutes=160), 'remarks': str(complaint), **audit()})

    recall = did('recall:001')
    created += await ensure(session, Recall, 'recall_id', recall, {
        'production_batch_id': production, 'reason': 'Demo recall dari complaint PKG-2026-0001.',
        'started_at': BASE + timedelta(minutes=170), 'completed_at': None, **audit()})
    recall_asset = await sync(session, 'RECALL', recall)
    created += await ensure(session, AssetRelationship, 'relationship_uuid', did('rel:production-recall'), {
        'parent_uuid': production_asset['asset_uuid'], 'child_uuid': recall_asset['asset_uuid'],
        'relationship_type': 'RECALLED', **audit()})
    created += await ensure(session, RecallWithdrawal, 'withdrawal_id', did('recall-withdrawal:001'), {
        'recall_id': recall, 'package_id': package, 'evidence_code': 'WD-PKG-2026-0001',
        'quantity': Decimal('2.000'), 'uom': 'portion', 'condition_note': 'Sisa sampel diamankan sekolah.',
        'photo': 'example/recall/withdrawal-pkg-2026-0001.jpg', 'withdrawn_at': BASE + timedelta(minutes=190),
        'completed_at': BASE + timedelta(minutes=195), **audit()})
    for event_type, entity_type, entity_uuid, payload in [
        ('complaint.recorded', 'COMPLAINT', complaint, {'schema_version': 1, 'actor_id': str(ACTOR), 'complaint_id': str(complaint)}),
        ('recall.started', 'RECALL', recall, {'schema_version': 1, 'actor_id': str(ACTOR), 'recall_id': str(recall)}),
        ('recall.withdrawal_recorded', 'RECALL', recall, {'schema_version': 1, 'actor_id': str(ACTOR), 'recall_id': str(recall)}),
    ]:
        created += await ensure(session, EventLog, 'event_uuid', did(f'event:{event_type}'), {
            'event_type': event_type, 'entity_type': entity_type, 'entity_uuid': entity_uuid,
            'payload': payload, **audit()})
    created += await ensure(session, NotificationOutbox, 'notification_id', did('notification:recall-pending'), {
        'entity_type': 'RECALL', 'entity_uuid': recall, 'event_type': 'recall.started', 'channel': 'DASHBOARD',
        'recipient': None, 'subject': 'Recall started', 'message': 'Demo recall MO-2026-0001 menunggu tindakan.',
        'status': 'PENDING', 'scheduled_at': BASE + timedelta(minutes=170), 'sent_at': None,
        'failure_reason': None, **audit()})

    return {
        'tenant_id': str(TENANT),
        'username': 'frontend-admin',
        'password': PASSWORD,
        'created': int(created),
        'created_grants': int(grant_count),
        'demo': {
            'package_code': 'PKG-2026-0001',
            'production_batch_code': 'MO-2026-0001',
            'complaint_id': str(complaint),
            'recall_id': str(recall),
            'vehicle_code': 'VH-BOX-01',
            'school_code': 'SCH-DEMO-01',
        },
    }


async def main():
    try:
        settings = get_settings()
        if settings.environment not in {'development', 'testing'}:
            raise ValueError('Demo seed requires ENVIRONMENT=development or testing')
        factory = async_sessionmaker(get_admin_engine())
        async with factory() as session, session.begin():
            result = await seed(session)
        print(json.dumps(result, default=str))
        return 0
    except Exception as exc:  # noqa: BLE001 - keep secrets/URLs out of logs
        print(json.dumps({'error_type': type(exc).__name__,
                          'detail': str(exc),
                          'action': 'Check ENVIRONMENT, ADMIN_DATABASE_URL, migration head 0032, telemetry partitions and fixture conflicts.'}))
        return 1
    finally:
        await close_database()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
