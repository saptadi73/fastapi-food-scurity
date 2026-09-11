from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.scope import ActorScope, InvalidActorError
from app.modules.authentication.infrastructure.orm import (
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)
from app.modules.master.infrastructure.orm import Tenant


class PermissionDeniedError(Exception):
    pass


async def require_permission(session: AsyncSession, scope: ActorScope, code: str) -> None:
    """Database authorization for a trusted identity; not a token authenticator."""
    user, tenant = User.__table__, Tenant.__table__
    actor = await session.scalar(select(user.c.user_id).join(
        tenant, user.c.tenant_id == tenant.c.tenant_id,
    ).where(
        user.c.user_id == scope.actor_id, user.c.tenant_id == scope.tenant_id,
        user.c.status == 'ACTIVE', tenant.c.status == 'ACTIVE',
        user.c.deleted_at.is_(None), tenant.c.deleted_at.is_(None),
    ).with_for_update(read=True))
    if actor is None:
        raise InvalidActorError('Active actor and tenant required')
    ur, role, rp, permission = (model.__table__ for model in (UserRole, Role, RolePermission, Permission))
    query = select(permission.c.permission_id).select_from(ur).join(
        role, (ur.c.tenant_id == role.c.tenant_id) & (ur.c.role_id == role.c.role_id),
    ).join(rp, (role.c.tenant_id == rp.c.tenant_id) & (role.c.role_id == rp.c.role_id)).join(
        permission, (rp.c.tenant_id == permission.c.tenant_id) & (rp.c.permission_id == permission.c.permission_id),
    ).where(ur.c.user_id == scope.actor_id, permission.c.permission_code == code)
    for table in (ur, role, rp, permission):
        query = query.where(table.c.tenant_id == scope.tenant_id, table.c.deleted_at.is_(None))
    # Locks keep a concurrent revocation from invalidating an in-flight authorized write.
    if await session.scalar(query.limit(1).with_for_update(read=True)) is None:
        raise PermissionDeniedError('Required permission is not granted')
