"""Seed exhibition/live-demo master data for a dedicated tenant (FSOS_EXPO).

Additive and idempotent, like seed_demo_ready.py. Never deletes or resets existing
data. Only creates the *master* records assumed already registered before a live
demo: tenant/login, kitchen/storage/zones, suppliers (multiple sources per some
materials), raw materials, schools (many, with varying student_count), a
vehicle/driver, packaging types, and several menus with recipes.

No receiving/production/packaging/delivery transaction is created here; the live
end-to-end flow is driven separately through the real HTTP API by
`demo_live_flow.py`, and the pre-built incident/traceability scenario is created
by `seed_exhibition_incident.py`. Guard: only runs on development/testing.
"""
import argparse
import asyncio
import json
import sys
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid5

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config.settings import get_settings
from app.core.database.location_permissions import LOCATION_PERMISSIONS
from app.core.database.receiving_permissions import RECEIVING_PERMISSIONS
from app.core.database.scope import ActorScope
from app.core.database.session import close_database, get_admin_engine
from app.core.database.supply_permissions import SUPPLY_PERMISSIONS
from app.modules.authentication.infrastructure.orm import (
    Permission,
    Role,
    RolePermission,
    User,
    UserLocationAssignment,
    UserRole,
)
from app.modules.authentication.infrastructure.passwords import hash_password_async
from app.modules.master.infrastructure.orm import (
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
from app.modules.traceability.infrastructure.registry import sync_source

NS = UUID('c3f7e6d2-df3a-4d61-9b8b-0a2c8e7f5b31')
DEFAULT_TENANT_CODE = 'FSOS_EXPO'
PASSWORD = 'ExpoDemo123!'
GURU_PASSWORD = 'GuruExpo123!'
OPERATOR_PASSWORD = 'OperatorExpo123!'


def scoped(tenant_code: str, name: str) -> UUID:
    """Deterministic UUID namespaced per tenant_code so separate exhibition tenants never collide."""
    return uuid5(NS, f'{tenant_code}:{name}')


async def ensure(session, model, pk_name: str, pk: UUID, values: dict) -> bool:
    table = model.__table__
    existing = await session.scalar(select(table.c[pk_name]).where(table.c[pk_name] == pk))
    if existing is not None:
        return False
    # Tenant-scoped rows may already contain the primary key in audit().
    # Merge before passing kwargs so SQLAlchemy never receives a duplicate key.
    payload = {**values, pk_name: pk}
    await session.execute(insert(table).values(**payload))
    return True


async def seed(session, *, username: str, tenant_code: str) -> dict:
    TENANT = scoped(tenant_code, 'tenant')
    ACTOR = scoped(tenant_code, 'actor')
    ROLE = scoped(tenant_code, 'role:expo-admin')

    def did(name: str) -> UUID:
        return scoped(tenant_code, name)

    def audit() -> dict:
        return {'tenant_id': TENANT, 'created_by': ACTOR, 'updated_by': ACTOR}

    async def ensure_permission(code: str) -> UUID:
        row = (await session.execute(select(Permission.__table__).where(
            Permission.tenant_id == TENANT, Permission.permission_code == code,
        ))).mappings().one_or_none()
        if row is not None:
            return row['permission_id']
        pid = did(f'permission:{code}')
        await session.execute(insert(Permission.__table__).values(
            permission_id=pid, permission_code=code, description=f'Expo demo permission {code}', **audit(),
        ))
        return pid

    async def ensure_grant(role_id: UUID, permission_id: UUID) -> bool:
        exists = await session.scalar(select(RolePermission.role_permission_id).where(
            RolePermission.tenant_id == TENANT, RolePermission.role_id == role_id,
            RolePermission.permission_id == permission_id,
        ))
        if exists is not None:
            return False
        await session.execute(insert(RolePermission.__table__).values(
            role_permission_id=did(f'grant:{role_id}:{permission_id}'), role_id=role_id, permission_id=permission_id, **audit(),
        ))
        return True

    async def sync(asset_type: str, entity_id: UUID) -> dict:
        return await sync_source(session, ActorScope(TENANT, ACTOR), asset_type, entity_id)

    created = 0
    created += await ensure(session, Tenant, 'tenant_id', TENANT, {
        'tenant_code': tenant_code, 'tenant_name': f'FSOS Exhibition Demo ({tenant_code})', 'status': 'ACTIVE', **audit(),
    })
    password_hash = await hash_password_async(PASSWORD)
    created += await ensure(session, User, 'user_id', ACTOR, {
        'tenant_id': TENANT, 'username': username, 'fullname': 'Exhibition Demo Operator',
        'email': 'expo-admin@example.invalid', 'password_hash': password_hash, 'status': 'ACTIVE', **audit(),
    })
    created += await ensure(session, Role, 'role_id', ROLE, {
        'tenant_id': TENANT, 'role_code': 'EXPO_ADMIN', 'role_name': 'Exhibition Demo Admin', **audit(),
    })
    created += await ensure(session, UserRole, 'user_role_id', did('user-role:expo-admin'), {
        'tenant_id': TENANT, 'user_id': ACTOR, 'role_id': ROLE, **audit(),
    })
    grant_count = 0
    all_permissions = sorted(set(LOCATION_PERMISSIONS) | set(SUPPLY_PERMISSIONS) | set(RECEIVING_PERMISSIONS))
    for code in all_permissions:
        grant_count += await ensure_grant(ROLE, await ensure_permission(code))

    # Role_code convention for registration: ADMIN (full access, same grants as EXPO_ADMIN),
    # GURU (signs school receiving at an assigned school) and OPERATOR_SEKOLAH (records the
    # school receiving/consumption itself). There is no student login; siswa are recipients
    # only, tracked via School.student_count.
    role_admin, role_guru, role_operator = did('role:admin'), did('role:guru'), did('role:operator-sekolah')
    created += await ensure(session, Role, 'role_id', role_admin, {
        'tenant_id': TENANT, 'role_code': 'ADMIN', 'role_name': 'Administrator', **audit(),
    })
    created += await ensure(session, Role, 'role_id', role_guru, {
        'tenant_id': TENANT, 'role_code': 'GURU', 'role_name': 'Guru Penanda Tangan Penerimaan', **audit(),
    })
    created += await ensure(session, Role, 'role_id', role_operator, {
        'tenant_id': TENANT, 'role_code': 'OPERATOR_SEKOLAH', 'role_name': 'Operator Penerimaan Sekolah', **audit(),
    })
    created += await ensure(session, UserRole, 'user_role_id', did('user-role:admin'), {
        'tenant_id': TENANT, 'user_id': ACTOR, 'role_id': role_admin, **audit(),
    })
    for code in all_permissions:
        grant_count += await ensure_grant(role_admin, await ensure_permission(code))
    for code in ('SchoolReceiving.Read', 'SchoolReceiving.Sign', 'Signature.Verify', 'Complaint.Read',
                'Complaint.Write', 'Complaint.Sign', 'Consumption.Read'):
        grant_count += await ensure_grant(role_guru, await ensure_permission(code))
    for code in ('SchoolReceiving.Read', 'SchoolReceiving.Write', 'Consumption.Read', 'Consumption.Write',
                'Complaint.Read', 'Complaint.Write', 'Package.Read', 'Delivery.Read', 'Traceability.Read'):
        grant_count += await ensure_grant(role_operator, await ensure_permission(code))

    kitchen = did('kitchen:pusat')
    cold, dry = did('storage:cold'), did('storage:dry')
    zone_cold, zone_dry = did('zone:cold-a'), did('zone:dry-a')
    sup_tani, sup_ternak, sup_sayur = did('supplier:tani'), did('supplier:ternak'), did('supplier:sayur')
    rice, chicken, carrot = did('material:rice'), did('material:chicken'), did('material:carrot')
    spinach, oil, egg = did('material:spinach'), did('material:oil'), did('material:egg')
    driver = did('driver:andi')
    vehicle = did('vehicle:box-01')
    pkg_lunchbox, pkg_ricebox = did('packaging:lunchbox'), did('packaging:ricebox')
    menu_utama, menu_telur, menu_wortel = did('food:menu-utama'), did('food:menu-telur'), did('food:menu-wortel')
    schools = [did(f'school:{i}') for i in range(1, 5)]

    masters = [
        (Kitchen, 'kitchen_id', kitchen, {'kitchen_code': 'DKP-EXPO', 'kitchen_name': 'Dapur Pusat Pameran',
            'latitude': Decimal('-6.200000'), 'longitude': Decimal('106.816666'), 'address': 'Jl. Pameran Pangan 1',
            'capacity': 3000, 'status': 'ACTIVE', **audit()}),
        (Storage, 'storage_id', cold, {'kitchen_id': kitchen, 'storage_code': 'COLD-EXPO',
            'storage_name': 'Cold Room Pameran', 'storage_type': 'COLD_STORAGE', 'temperature_min': Decimal('1.00'),
            'temperature_max': Decimal('5.00'), 'status': 'ACTIVE', **audit()}),
        (Storage, 'storage_id', dry, {'kitchen_id': kitchen, 'storage_code': 'DRY-EXPO',
            'storage_name': 'Dry Storage Pameran', 'storage_type': 'DRY_STORAGE', 'temperature_min': Decimal('20.00'),
            'temperature_max': Decimal('30.00'), 'status': 'ACTIVE', **audit()}),
        (StorageZone, 'zone_id', zone_cold, {'storage_id': cold, 'zone_code': 'COLD-A1', 'zone_name': 'Rak Chiller A1', **audit()}),
        (StorageZone, 'zone_id', zone_dry, {'storage_id': dry, 'zone_code': 'DRY-A1', 'zone_name': 'Rak Kering A1', **audit()}),
        (Supplier, 'supplier_id', sup_tani, {'supplier_code': 'SUP-EXPO-01', 'supplier_name': 'Koperasi Tani Sejahtera',
            'phone': '0811100001', 'email': 'tani@example.invalid', 'status': 'ACTIVE', **audit()}),
        (Supplier, 'supplier_id', sup_ternak, {'supplier_code': 'SUP-EXPO-02', 'supplier_name': 'Peternakan Ayam Barokah',
            'phone': '0811100002', 'email': 'ternak@example.invalid', 'status': 'ACTIVE', **audit()}),
        (Supplier, 'supplier_id', sup_sayur, {'supplier_code': 'SUP-EXPO-03', 'supplier_name': 'Distributor Sayur Segar Nusantara',
            'phone': '0811100003', 'email': 'sayur@example.invalid', 'status': 'ACTIVE', **audit()}),
        (RawMaterial, 'raw_material_id', rice, {'material_code': 'RM-EXPO-BERAS', 'material_name': 'Beras Premium Expo',
            'category': 'CARBOHYDRATE', 'uom': 'kg', 'storage_type': 'DRY_STORAGE',
            'recommended_temperature_min': Decimal('20.00'), 'recommended_temperature_max': Decimal('30.00'),
            'maximum_storage_hours': Decimal('720.00'), 'status': 'ACTIVE', **audit()}),
        (RawMaterial, 'raw_material_id', chicken, {'material_code': 'RM-EXPO-AYAM', 'material_name': 'Ayam Fillet Expo',
            'category': 'PROTEIN', 'uom': 'kg', 'storage_type': 'COLD_STORAGE',
            'recommended_temperature_min': Decimal('1.00'), 'recommended_temperature_max': Decimal('5.00'),
            'maximum_storage_hours': Decimal('48.00'), 'status': 'ACTIVE', **audit()}),
        (RawMaterial, 'raw_material_id', carrot, {'material_code': 'RM-EXPO-WORTEL', 'material_name': 'Wortel Segar Expo',
            'category': 'VEGETABLE', 'uom': 'kg', 'storage_type': 'COLD_STORAGE',
            'recommended_temperature_min': Decimal('2.00'), 'recommended_temperature_max': Decimal('8.00'),
            'maximum_storage_hours': Decimal('120.00'), 'status': 'ACTIVE', **audit()}),
        (RawMaterial, 'raw_material_id', spinach, {'material_code': 'RM-EXPO-BAYAM', 'material_name': 'Bayam Segar Expo',
            'category': 'VEGETABLE', 'uom': 'kg', 'storage_type': 'COLD_STORAGE',
            'recommended_temperature_min': Decimal('2.00'), 'recommended_temperature_max': Decimal('8.00'),
            'maximum_storage_hours': Decimal('48.00'), 'status': 'ACTIVE', **audit()}),
        (RawMaterial, 'raw_material_id', oil, {'material_code': 'RM-EXPO-MINYAK', 'material_name': 'Minyak Goreng Expo',
            'category': 'FAT', 'uom': 'liter', 'storage_type': 'DRY_STORAGE',
            'recommended_temperature_min': Decimal('20.00'), 'recommended_temperature_max': Decimal('30.00'),
            'maximum_storage_hours': Decimal('4320.00'), 'status': 'ACTIVE', **audit()}),
        (RawMaterial, 'raw_material_id', egg, {'material_code': 'RM-EXPO-TELUR', 'material_name': 'Telur Ayam Expo',
            'category': 'PROTEIN', 'uom': 'kg', 'storage_type': 'COLD_STORAGE',
            'recommended_temperature_min': Decimal('2.00'), 'recommended_temperature_max': Decimal('8.00'),
            'maximum_storage_hours': Decimal('336.00'), 'status': 'ACTIVE', **audit()}),
        (SupplierMaterial, 'supplier_material_id', did('sm:tani:rice'), {'supplier_id': sup_tani, 'raw_material_id': rice, **audit()}),
        (SupplierMaterial, 'supplier_material_id', did('sm:ternak:chicken'), {'supplier_id': sup_ternak, 'raw_material_id': chicken, **audit()}),
        (SupplierMaterial, 'supplier_material_id', did('sm:sayur:carrot'), {'supplier_id': sup_sayur, 'raw_material_id': carrot, **audit()}),
        (SupplierMaterial, 'supplier_material_id', did('sm:sayur:spinach'), {'supplier_id': sup_sayur, 'raw_material_id': spinach, **audit()}),
        # Bahan dengan lebih dari satu sumber pemasok, untuk menunjukkan variasi asal bahan.
        (SupplierMaterial, 'supplier_material_id', did('sm:tani:oil'), {'supplier_id': sup_tani, 'raw_material_id': oil, **audit()}),
        (SupplierMaterial, 'supplier_material_id', did('sm:sayur:oil'), {'supplier_id': sup_sayur, 'raw_material_id': oil, **audit()}),
        (SupplierMaterial, 'supplier_material_id', did('sm:ternak:egg'), {'supplier_id': sup_ternak, 'raw_material_id': egg, **audit()}),
        (SupplierMaterial, 'supplier_material_id', did('sm:tani:egg'), {'supplier_id': sup_tani, 'raw_material_id': egg, **audit()}),
        (Driver, 'driver_id', driver, {'driver_code': 'DRV-EXPO-01', 'driver_name': 'Andi Setiawan',
            'phone': '0811200001', 'status': 'ACTIVE', **audit()}),
        (Vehicle, 'vehicle_id', vehicle, {'vehicle_code': 'VH-EXPO-01', 'plate_number': 'B 1234 EXP',
            'vehicle_type': 'BOX', 'capacity': Decimal('500.00'), 'gps_device': None, 'driver_id': driver,
            'latitude': Decimal('-6.200000'), 'longitude': Decimal('106.816666'), 'status': 'ACTIVE', **audit()}),
        (PackagingType, 'package_type_id', pkg_lunchbox, {'code': 'PKG-EXPO-LB', 'name': 'Lunch Box 750ml',
            'material': 'Food grade PP', 'volume': Decimal('750.000'), **audit()}),
        (PackagingType, 'package_type_id', pkg_ricebox, {'code': 'PKG-EXPO-RB', 'name': 'Rice Box 500ml',
            'material': 'Food grade PP', 'volume': Decimal('500.000'), **audit()}),
        (FoodItem, 'food_item_id', menu_utama, {'food_code': 'MENU-EXPO-UTAMA', 'food_name': 'Nasi Ayam Sayur Expo',
            'category': 'HOT_MEAL', 'uom': 'porsi', 'holding_limit_minutes': 120, 'status': 'ACTIVE', **audit()}),
        (FoodItem, 'food_item_id', menu_telur, {'food_code': 'MENU-EXPO-TELUR', 'food_name': 'Nasi Telur Bayam Expo',
            'category': 'HOT_MEAL', 'uom': 'porsi', 'holding_limit_minutes': 120, 'status': 'ACTIVE', **audit()}),
        (FoodItem, 'food_item_id', menu_wortel, {'food_code': 'MENU-EXPO-WORTEL', 'food_name': 'Nasi Ayam Wortel Expo',
            'category': 'HOT_MEAL', 'uom': 'porsi', 'holding_limit_minutes': 120, 'status': 'ACTIVE', **audit()}),
        (Recipe, 'recipe_id', did('recipe:utama:rice'), {'food_item_id': menu_utama, 'raw_material_id': rice,
            'quantity': Decimal('0.150000'), 'uom': 'kg', **audit()}),
        (Recipe, 'recipe_id', did('recipe:utama:chicken'), {'food_item_id': menu_utama, 'raw_material_id': chicken,
            'quantity': Decimal('0.080000'), 'uom': 'kg', **audit()}),
        (Recipe, 'recipe_id', did('recipe:telur:rice'), {'food_item_id': menu_telur, 'raw_material_id': rice,
            'quantity': Decimal('0.150000'), 'uom': 'kg', **audit()}),
        (Recipe, 'recipe_id', did('recipe:telur:egg'), {'food_item_id': menu_telur, 'raw_material_id': egg,
            'quantity': Decimal('0.060000'), 'uom': 'kg', **audit()}),
        (Recipe, 'recipe_id', did('recipe:telur:spinach'), {'food_item_id': menu_telur, 'raw_material_id': spinach,
            'quantity': Decimal('0.050000'), 'uom': 'kg', **audit()}),
        (Recipe, 'recipe_id', did('recipe:wortel:rice'), {'food_item_id': menu_wortel, 'raw_material_id': rice,
            'quantity': Decimal('0.150000'), 'uom': 'kg', **audit()}),
        (Recipe, 'recipe_id', did('recipe:wortel:chicken'), {'food_item_id': menu_wortel, 'raw_material_id': chicken,
            'quantity': Decimal('0.080000'), 'uom': 'kg', **audit()}),
        (Recipe, 'recipe_id', did('recipe:wortel:carrot'), {'food_item_id': menu_wortel, 'raw_material_id': carrot,
            'quantity': Decimal('0.040000'), 'uom': 'kg', **audit()}),
    ]
    for i, (school_id, code, name, student_count) in enumerate([
        (schools[0], 'SCH-EXPO-01', 'SD Expo Mandiri 1', 120),
        (schools[1], 'SCH-EXPO-02', 'SD Expo Mandiri 2', 300),
        (schools[2], 'SCH-EXPO-03', 'SD Expo Mandiri 3', 450),
        (schools[3], 'SCH-EXPO-04', 'SD Expo Mandiri 4', 220),
    ]):
        masters.append((School, 'school_id', school_id, {'kitchen_id': kitchen, 'school_code': code,
            'school_name': name, 'latitude': Decimal(f'-6.2{10 + i}000'), 'longitude': Decimal(f'106.8{20 + i}000'),
            'address': f'Jl. Sekolah Pameran {i + 1}', 'student_count': student_count, 'status': 'ACTIVE', **audit()}))

    for model, pk_name, pk, values in masters:
        created += await ensure(session, model, pk_name, pk, values)

    # Demo signer accounts for the GURU/OPERATOR_SEKOLAH role convention, assigned to school 1
    # so SchoolReceiving.Sign's active-assignment check passes during the live demo. Distinct
    # passwords from ADMIN so a mistyped username does not silently log in as the wrong role.
    guru_user, operator_user = did('user:guru-01'), did('user:operator-01')
    guru_password_hash = await hash_password_async(GURU_PASSWORD)
    operator_password_hash = await hash_password_async(OPERATOR_PASSWORD)
    created += await ensure(session, User, 'user_id', guru_user, {
        'tenant_id': TENANT, 'username': 'guru-sd-expo-01', 'fullname': 'Siti Guru SD Expo 1',
        'job_title': 'Guru Kelas', 'email': 'guru-sd-expo-01@example.invalid',
        'password_hash': guru_password_hash, 'status': 'ACTIVE', **audit(),
    })
    created += await ensure(session, User, 'user_id', operator_user, {
        'tenant_id': TENANT, 'username': 'operator-sd-expo-01', 'fullname': 'Budi Operator SD Expo 1',
        'job_title': 'Operator Penerimaan', 'email': 'operator-sd-expo-01@example.invalid',
        'password_hash': operator_password_hash, 'status': 'ACTIVE', **audit(),
    })
    created += await ensure(session, UserRole, 'user_role_id', did('user-role:guru-01'), {
        'tenant_id': TENANT, 'user_id': guru_user, 'role_id': role_guru, **audit(),
    })
    created += await ensure(session, UserRole, 'user_role_id', did('user-role:operator-01'), {
        'tenant_id': TENANT, 'user_id': operator_user, 'role_id': role_operator, **audit(),
    })
    created += await ensure(session, UserLocationAssignment, 'assignment_id', did('assignment:guru-01'), {
        'tenant_id': TENANT, 'user_id': guru_user, 'location_type': 'SCHOOL', 'kitchen_id': None,
        'school_id': schools[0], **audit(),
    })
    created += await ensure(session, UserLocationAssignment, 'assignment_id', did('assignment:operator-01'), {
        'tenant_id': TENANT, 'user_id': operator_user, 'location_type': 'SCHOOL', 'kitchen_id': None,
        'school_id': schools[0], **audit(),
    })

    for asset_type, entity in [
        ('KITCHEN', kitchen), ('STORAGE', cold), ('STORAGE', dry),
        ('SUPPLIER', sup_tani), ('SUPPLIER', sup_ternak), ('SUPPLIER', sup_sayur),
        ('RAW_MATERIAL', rice), ('RAW_MATERIAL', chicken), ('RAW_MATERIAL', carrot),
        ('RAW_MATERIAL', spinach), ('RAW_MATERIAL', oil), ('RAW_MATERIAL', egg),
        ('VEHICLE', vehicle), *[('SCHOOL', school_id) for school_id in schools],
    ]:
        await sync(asset_type, entity)

    return {
        'tenant_id': str(TENANT), 'tenant_code': tenant_code, 'username': username, 'password': PASSWORD,
        'created': int(created), 'created_grants': int(grant_count),
        'kitchen_code': 'DKP-EXPO', 'menu_code_for_live_demo': 'MENU-EXPO-UTAMA',
        'materials_for_live_demo': ['RM-EXPO-BERAS', 'RM-EXPO-AYAM'],
        'suppliers_for_live_demo': ['SUP-EXPO-01', 'SUP-EXPO-02'],
        'schools': ['SCH-EXPO-01', 'SCH-EXPO-02', 'SCH-EXPO-03', 'SCH-EXPO-04'],
        'vehicle_code': 'VH-EXPO-01', 'driver_code': 'DRV-EXPO-01',
        'roles': {'ADMIN': username, 'GURU': 'guru-sd-expo-01', 'OPERATOR_SEKOLAH': 'operator-sd-expo-01'},
        'role_passwords': {'ADMIN': PASSWORD, 'GURU': GURU_PASSWORD, 'OPERATOR_SEKOLAH': OPERATOR_PASSWORD},
        'note': 'No SISWA login; siswa are recipients only via School.student_count, not user accounts.',
    }


async def main():
    try:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--username', default='expo-admin', help='Login username; default expo-admin')
        parser.add_argument('--tenant-code', default=DEFAULT_TENANT_CODE,
                            help='Tenant code to create/seed; use a distinct code (e.g. FSOS_EXPO_INCIDENT) '
                                 'to keep the incident/recall scenario isolated from the live demo tenant')
        args = parser.parse_args()
        settings = get_settings()
        if settings.environment not in {'development', 'testing'}:
            raise ValueError('Exhibition seed requires ENVIRONMENT=development or testing')
        factory = async_sessionmaker(get_admin_engine())
        async with factory() as session, session.begin():
            result = await seed(session, username=args.username, tenant_code=args.tenant_code)
        print(json.dumps(result, default=str, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001 - keep secrets/URLs out of logs
        print(json.dumps({'error_type': type(exc).__name__, 'detail': str(exc),
                          'action': 'Check ENVIRONMENT, ADMIN_DATABASE_URL and migration head.'}))
        return 1
    finally:
        await close_database()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
