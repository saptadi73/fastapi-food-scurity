"""Administrative development provisioning; never expose this helper as a public signup API."""
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import func, insert, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.authentication.infrastructure.orm import Role, User, UserRole
from app.modules.authentication.infrastructure.passwords import hash_password_async
from app.modules.master.infrastructure.orm import Tenant


class BootstrapConflictError(Exception):
    pass


class HumanAccountInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tenant_id: UUID
    actor_id: UUID
    username: str = Field(min_length=1, max_length=100, strict=True)
    fullname: str = Field(min_length=1, max_length=200, strict=True)
    email: EmailStr = Field(max_length=254)
    role_ids: list[UUID] = Field(min_length=1, max_length=100)

    @field_validator('username', 'fullname')
    @classmethod
    def clean_text(cls, value):
        value = value.strip(' ')
        if not value or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError('Nonblank text without control characters required')
        try:
            value.encode('utf-8')
        except UnicodeEncodeError:
            raise ValueError('Valid UTF-8 required') from None
        return value

    @field_validator('role_ids')
    @classmethod
    def unique_roles(cls, value):
        if len(value) != len(set(value)):
            raise ValueError('Role identifiers must be unique')
        return value


async def check_human_account(session: AsyncSession, payload: HumanAccountInput, *, environment: str) -> dict:
    if environment != 'development':
        raise ValueError('Human bootstrap currently supports development only')
    # Serialize administrative bootstrap within a tenant; uniqueness also protects against raw SQL races.
    await session.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:tenant, 53))'), {'tenant': str(payload.tenant_id)})
    u, t, r = User.__table__, Tenant.__table__, Role.__table__
    actor = await session.scalar(select(u.c.user_id).join(t, u.c.tenant_id == t.c.tenant_id).where(
        u.c.tenant_id == payload.tenant_id, u.c.user_id == payload.actor_id,
        u.c.status == 'ACTIVE', t.c.status == 'ACTIVE', u.c.deleted_at.is_(None), t.c.deleted_at.is_(None),
    ).with_for_update(read=True))
    if actor is None:
        raise BootstrapConflictError('Active audit actor and tenant required')
    exists = await session.scalar(select(u.c.user_id).where(u.c.tenant_id == payload.tenant_id, or_(
        func.lower(func.btrim(u.c.username)) == func.lower(func.btrim(payload.username)),
        func.lower(func.btrim(u.c.email)) == func.lower(func.btrim(str(payload.email))),
    )).limit(1))
    if exists is not None:
        raise BootstrapConflictError('Username or email already reserved; existing accounts are never changed')
    roles = (await session.execute(select(r.c.role_id, r.c.role_code).where(
        r.c.tenant_id == payload.tenant_id, r.c.role_id.in_(payload.role_ids), r.c.deleted_at.is_(None),
    ).with_for_update(read=True))).mappings().all()
    if len(roles) != len(payload.role_ids):
        raise BootstrapConflictError('Every selected role must exist and be active in the tenant')
    return {'tenant_id': payload.tenant_id, 'actor_id': payload.actor_id, 'username': payload.username,
            'fullname': payload.fullname, 'email': str(payload.email),
            'roles': sorted(row['role_code'] for row in roles), 'will_create': True}


async def create_human_account(session: AsyncSession, payload: HumanAccountInput,
                               password: str, *, environment: str) -> dict:
    if environment != 'development':
        raise ValueError('Human bootstrap currently supports development only')
    # Hash before locks, then revalidate all identities/roles in the write transaction.
    hashed = await hash_password_async(password)
    result = await check_human_account(session, payload, environment=environment)
    identifier = uuid4()
    await session.execute(insert(User.__table__).values(
        user_id=identifier, tenant_id=payload.tenant_id, username=payload.username,
        fullname=payload.fullname, email=str(payload.email), password_hash=hashed, status='ACTIVE',
        created_by=payload.actor_id, updated_by=payload.actor_id, version=1,
    ))
    for role_id in sorted(payload.role_ids):
        await session.execute(insert(UserRole.__table__).values(
            user_role_id=uuid4(), tenant_id=payload.tenant_id, user_id=identifier, role_id=role_id,
            created_by=payload.actor_id, updated_by=payload.actor_id, version=1,
        ))
    return {k: v for k, v in {**result, 'user_id': identifier, 'created': True}.items() if k != 'will_create'}
