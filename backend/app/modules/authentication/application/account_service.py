"""Account authentication for trusted application callers; no HTTP/refresh session yet."""
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.scope import ActorScope
from app.modules.authentication.infrastructure.access_tokens import AccessTokenCodec
from app.modules.authentication.infrastructure.orm import (
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)
from app.modules.authentication.infrastructure.passwords import verify_login_password_async
from app.modules.master.infrastructure.orm import Tenant


class InvalidCredentialsError(Exception):
    pass


@dataclass(frozen=True)
class AuthenticatedAccount:
    user_id: UUID
    tenant_id: UUID
    roles: tuple[str, ...]
    permissions: tuple[str, ...]


class AccountService:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _active_query(self, tenant_id):
        u, t = User.__table__, Tenant.__table__
        return select(u.c.user_id, u.c.password_hash).join(t, u.c.tenant_id == t.c.tenant_id).where(
            u.c.tenant_id == tenant_id, u.c.status == 'ACTIVE', t.c.status == 'ACTIVE',
            u.c.deleted_at.is_(None), t.c.deleted_at.is_(None),
        )

    async def authenticate(self, tenant_id: UUID, username: str, password: str) -> AuthenticatedAccount:
        valid = (isinstance(tenant_id, UUID) and isinstance(username, str)
                 and 0 < len(username) <= 100 and bool(username.strip(' ')) and '\x00' not in username)
        if valid:
            try:
                username.encode('utf-8')
            except UnicodeEncodeError:
                valid = False
        row = None
        if valid:
            row = (await self.session.execute(self._active_query(tenant_id).where(
                func.lower(func.btrim(User.username)) == func.lower(func.btrim(username)),
            ))).mappings().one_or_none()
        matched = await verify_login_password_async(password, row['password_hash'] if row else None)
        if not matched or row is None:
            raise InvalidCredentialsError('Invalid credentials')
        # Expensive bcrypt ran before locks. Recheck password/status under locks before authorizing.
        current = (await self.session.execute(self._active_query(tenant_id).where(
            User.user_id == row['user_id'],
        ).with_for_update(read=True))).mappings().one_or_none()
        if current is None or current['password_hash'] != row['password_hash']:
            raise InvalidCredentialsError('Invalid credentials')
        return await self.snapshot(tenant_id, row['user_id'])

    async def snapshot(self, tenant_id: UUID, user_id: UUID) -> AuthenticatedAccount:
        current = await self.session.scalar(self._active_query(tenant_id).where(
            User.user_id == user_id,
        ).with_for_update(read=True))
        if current is None:
            raise InvalidCredentialsError('Invalid credentials')
        ur, role, rp, permission = (m.__table__ for m in (UserRole, Role, RolePermission, Permission))
        roles_query = select(role.c.role_code).select_from(ur).join(role,
            (ur.c.tenant_id == role.c.tenant_id) & (ur.c.role_id == role.c.role_id),
        ).where(ur.c.tenant_id == tenant_id, ur.c.user_id == user_id,
                ur.c.deleted_at.is_(None), role.c.deleted_at.is_(None))
        roles = (await self.session.execute(roles_query.with_for_update(read=True))).scalars().all()
        permissions_query = roles_query.with_only_columns(permission.c.permission_code).join(rp,
            (rp.c.tenant_id == role.c.tenant_id) & (rp.c.role_id == role.c.role_id),
        ).join(permission,
            (permission.c.tenant_id == rp.c.tenant_id) & (permission.c.permission_id == rp.c.permission_id),
        ).where(rp.c.deleted_at.is_(None), permission.c.deleted_at.is_(None))
        permissions = (await self.session.execute(permissions_query.with_for_update(read=True))).scalars().all()
        return AuthenticatedAccount(user_id, tenant_id, tuple(sorted(set(roles))), tuple(sorted(set(permissions))))

    async def resolve_access(self, token: str, codec: AccessTokenCodec) -> ActorScope:
        identity = codec.decode(token)
        user_id = await self.session.scalar(self._active_query(identity.tenant_id).where(
            User.user_id == identity.user_id,
        ).with_for_update(read=True))
        if user_id is None:
            raise InvalidCredentialsError('Invalid credentials')
        # Never use token permission snapshots to authorize an operation.
        return ActorScope(identity.tenant_id, identity.user_id)
