"""Explicit development administrative grants; no HTTP exposure or seed widening."""
from uuid import UUID, uuid4

from sqlalchemy import insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.authentication.infrastructure.orm import Permission, Role, RolePermission, User
from app.modules.master.infrastructure.orm import Tenant

SUPPLY_PERMISSIONS = ('PackagingType.Read', 'PackagingType.Write', 'PackagingType.Delete', 'FoodItem.Read', 'FoodItem.Write', 'FoodItem.Delete', 'Recipe.Read', 'Recipe.Write', 'Recipe.Delete', 'Supplier.Delete', 'RawMaterial.Delete', 'SupplierMaterial.Delete', 'Supplier.Read', 'Supplier.Write', 'RawMaterial.Read', 'RawMaterial.Write', 'SupplierMaterial.Read', 'SupplierMaterial.Write')


class SupplyGrantConflictError(Exception):
    pass


async def provision_supply_permissions(session: AsyncSession, *, tenant_id: UUID, actor_id: UUID,
                                          role_id: UUID, permissions: list[str], environment: str,
                                          apply: bool = False) -> dict:
    """Caller owns admin connection and transaction. Check mode never writes; revoked rows are not restored."""
    if environment != 'development':
        raise ValueError('Development only')
    if not permissions or len(permissions) != len(set(permissions)) or not set(permissions) <= set(SUPPLY_PERMISSIONS):
        raise ValueError('Choose unique supply permissions explicitly')
    if type(apply) is not bool:
        raise ValueError('Boolean apply required')
    await session.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:tenant, 56))'), {'tenant': str(tenant_id)})
    actor = await session.scalar(select(User.user_id).join(Tenant, User.tenant_id == Tenant.tenant_id).where(
        User.tenant_id == tenant_id, User.user_id == actor_id, User.status == 'ACTIVE',
        User.deleted_at.is_(None), Tenant.deleted_at.is_(None), Tenant.status == 'ACTIVE',
    ).with_for_update(read=True))
    role = await session.scalar(select(Role.role_id).where(Role.tenant_id == tenant_id, Role.role_id == role_id,
                                                         Role.deleted_at.is_(None)).with_for_update(read=True))
    if actor is None or role is None:
        raise SupplyGrantConflictError('Active actor, tenant and selected tenant role required')
    plan = []
    for code in sorted(permissions):
        permission = (await session.execute(select(Permission.__table__).where(
            Permission.tenant_id == tenant_id, Permission.permission_code == code,
        ).with_for_update())).mappings().one_or_none()
        if permission is not None and permission['deleted_at'] is not None:
            raise SupplyGrantConflictError('Revoked permission must be reviewed separately')
        grant = None
        if permission is not None:
            grant = (await session.execute(select(RolePermission.__table__).where(
                RolePermission.tenant_id == tenant_id, RolePermission.role_id == role_id,
                RolePermission.permission_id == permission['permission_id'],
            ).with_for_update())).mappings().one_or_none()
        if grant is not None and grant['deleted_at'] is not None:
            raise SupplyGrantConflictError('Revoked grant must be reviewed separately')
        plan.append((code, permission, grant))
    # Validate every requested grant before writing any row.
    for code, permission, grant in plan:
        if not apply:
            continue
        pid = permission['permission_id'] if permission is not None else uuid4()
        audit = {'tenant_id': tenant_id, 'created_by': actor_id, 'updated_by': actor_id}
        if permission is None:
            await session.execute(insert(Permission.__table__).values(permission_id=pid, permission_code=code, **audit))
        if grant is None:
            await session.execute(insert(RolePermission.__table__).values(role_permission_id=uuid4(), role_id=role_id, permission_id=pid, **audit))
    return {'mode': 'apply' if apply else 'check', 'tenant_id': tenant_id, 'role_id': role_id,
            'permissions': [code for code, _, _ in plan],
            'missing_permissions': sum(p is None for _, p, _ in plan),
            'missing_grants': sum(g is None for _, _, g in plan),
            'created_permissions': sum(p is None for _, p, _ in plan) if apply else 0,
            'created_grants': sum(g is None for _, _, g in plan) if apply else 0}
