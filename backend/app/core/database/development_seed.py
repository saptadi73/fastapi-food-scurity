"""Reserved development fixtures, additive and repeatable; never a production bootstrap."""
from uuid import UUID, uuid5

from sqlalchemy import insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.scope import ActorScope
from app.modules.authentication.infrastructure.orm import (
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)
from app.modules.master.infrastructure.orm import (
    Device,
    Kitchen,
    RawMaterial,
    School,
    Storage,
    StorageZone,
    Supplier,
    Tenant,
)
from app.modules.traceability.application.registry_service import RegistryService
from app.modules.traceability.infrastructure.registry import SOURCES

SEED_NAMESPACE = UUID('7f647332-3adf-4f41-b10f-05fdd686f0a3')
PERMISSIONS = ('AssetRegistry.Sync', 'AlarmRule.Read', 'AlarmRule.Write', 'AlarmRule.Activate',
               'HoldingRule.Read', 'HoldingRule.Write')


def seed_id(name: str) -> UUID:
    return uuid5(SEED_NAMESPACE, name)


class SeedConflictError(Exception):
    pass


async def seed_development(session: AsyncSession, *, environment: str) -> dict:
    if environment != 'development':
        raise ValueError('Development seed requires ENVIRONMENT=development')
    await session.execute(text('SELECT pg_advisory_xact_lock(20260911, 16)'))
    tenant, actor = seed_id('tenant'), seed_id('actor')
    existing_actor = await session.scalar(select(User.user_id).where(User.user_id == actor))
    created = 0

    async def ensure(model, label, identity, values=None):
        nonlocal created
        table = model.__table__
        pk = next(iter(table.primary_key.columns))
        identifier = seed_id(label)
        row = (await session.execute(select(table).where(pk == identifier).with_for_update())).mappings().one_or_none()
        if row is not None:
            if row['deleted_at'] is not None or any(row[k] != v for k, v in identity.items()):
                raise SeedConflictError(f'Development identity conflict: {label}')
            return identifier
        if existing_actor is not None and model in (Role, Permission, UserRole, RolePermission):
            raise SeedConflictError(f'Missing development grant or role: {label}')
        await session.execute(insert(table).values(
            **{pk.name: identifier}, **identity, **(values or {}), created_by=actor, updated_by=actor,
        ))
        created += 1
        return identifier

    await ensure(Tenant, 'tenant', {'tenant_code': 'FSOS_DEV', 'status': 'ACTIVE'}, {'tenant_name': 'FSOS Development'})
    await ensure(User, 'actor', {'tenant_id': tenant, 'username': 'dev-maintenance',
                               'email': 'dev-maintenance@example.invalid', 'status': 'ACTIVE'},
                 {'fullname': 'Development Maintenance', 'password_hash': None})
    role = await ensure(Role, 'role', {'tenant_id': tenant, 'role_code': 'DEV_MAINTENANCE'}, {'role_name': 'Development Maintenance'})
    await ensure(UserRole, 'user-role', {'tenant_id': tenant, 'user_id': actor, 'role_id': role})
    for code in PERMISSIONS:
        permission = await ensure(Permission, f'permission:{code}', {'tenant_id': tenant, 'permission_code': code})
        await ensure(RolePermission, f'grant:{code}', {'tenant_id': tenant, 'role_id': role, 'permission_id': permission})
    kitchen = await ensure(Kitchen, 'kitchen', {'tenant_id': tenant, 'kitchen_code': 'DEV_KITCHEN'},
                           {'kitchen_name': 'Dapur Demo', 'capacity': 100})
    storage = await ensure(Storage, 'storage', {'tenant_id': tenant, 'kitchen_id': kitchen, 'storage_code': 'DEV_STORAGE'},
                           {'storage_name': 'Penyimpanan Demo', 'storage_type': 'COLD_STORAGE'})
    zone = await ensure(StorageZone, 'zone', {'tenant_id': tenant, 'storage_id': storage, 'zone_code': 'DEV_ZONE'},
                        {'zone_name': 'Zona Demo'})
    await ensure(Device, 'device', {'tenant_id': tenant, 'device_uuid': seed_id('device-public'), 'zone_id': zone},
                 {'device_name': 'Sensor Demo', 'device_type': 'TEMPERATURE'})
    await ensure(Supplier, 'supplier', {'tenant_id': tenant, 'supplier_code': 'DEV_SUPPLIER'}, {'supplier_name': 'Pemasok Demo'})
    await ensure(RawMaterial, 'material', {'tenant_id': tenant, 'material_code': 'DEV_MATERIAL'},
                 {'material_name': 'Bahan Demo', 'uom': 'kg'})
    await ensure(School, 'school', {'tenant_id': tenant, 'kitchen_id': kitchen, 'school_code': 'DEV_SCHOOL'},
                 {'school_name': 'Sekolah Demo'})
    # Same transaction as fixtures: a failed backfill rolls back the entire seed.
    service = RegistryService(session, ActorScope(tenant, actor))
    processed = {}
    for kind in SOURCES:
        cursor, count = None, 0
        while True:
            batch = await service.backfill(kind, after_id=cursor)
            count += batch['processed']
            if not batch['processed']:
                break
            cursor = batch['last_id']
        processed[kind] = count
    return {'tenant_id': str(tenant), 'actor_id': str(actor), 'created': created, 'registry_processed': processed}
