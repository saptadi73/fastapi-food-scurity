"""First scoped repository; immutable evidence tables do not use this write path."""
from collections.abc import Mapping
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.scope import (
    ActorScope,
    InvalidActorError,
    RecordNotFoundError,
    VersionConflictError,
)
from app.modules.authentication.infrastructure.orm import User
from app.modules.master.infrastructure.orm import Kitchen, Tenant
from app.modules.traceability.infrastructure.registry import sync_source


class KitchenRepository:
    writable_fields = frozenset({
        "kitchen_code", "kitchen_name", "latitude", "longitude", "address", "capacity", "status",
    })

    def __init__(self, session: AsyncSession, scope: ActorScope):
        self.session = session
        self.scope = scope
        self.table = Kitchen.__table__

    async def _authorize(self):
        user, tenant = User.__table__, Tenant.__table__
        actor = await self.session.scalar(select(user.c.user_id).join(
            tenant, user.c.tenant_id == tenant.c.tenant_id,
        ).where(
            user.c.user_id == self.scope.actor_id,
            user.c.tenant_id == self.scope.tenant_id,
            user.c.deleted_at.is_(None), user.c.status == "ACTIVE",
            tenant.c.deleted_at.is_(None), tenant.c.status == "ACTIVE",
        ).with_for_update(read=True))
        if actor is None:
            raise InvalidActorError("Active actor in active tenant required")

    def _visible(self):
        return (self.table.c.tenant_id == self.scope.tenant_id, self.table.c.deleted_at.is_(None))

    def _fields(self, values: Mapping[str, Any]):
        if not values or set(values) - self.writable_fields:
            raise ValueError("Supply only writable kitchen fields")
        return dict(values)

    async def get(self, identifier: UUID) -> dict:
        await self._authorize()
        row = (await self.session.execute(select(self.table).where(
            *self._visible(), self.table.c.kitchen_id == identifier,
        ))).mappings().one_or_none()
        if row is None:
            raise RecordNotFoundError("Kitchen not found")
        return dict(row)

    async def list(self, *, offset: int = 0, limit: int = 20) -> list[dict]:
        if type(offset) is not int or type(limit) is not int or offset < 0 or not 1 <= limit <= 100:
            raise ValueError("offset >= 0 and limit between 1 and 100 required")
        await self._authorize()
        rows = (await self.session.execute(select(self.table).where(*self._visible()).order_by(
            self.table.c.created_at, self.table.c.kitchen_id,
        ).offset(offset).limit(limit))).mappings()
        return [dict(row) for row in rows]

    async def create(self, values: Mapping[str, Any]) -> dict:
        fields = self._fields(values)
        await self._authorize()
        row = (await self.session.execute(insert(self.table).values(
            **fields, kitchen_id=uuid4(), tenant_id=self.scope.tenant_id,
            created_by=self.scope.actor_id, updated_by=self.scope.actor_id, version=1,
        ).returning(self.table))).mappings().one()
        await sync_source(self.session, self.scope, 'KITCHEN', row['kitchen_id'])
        return dict(row)

    async def update(self, identifier: UUID, values: Mapping[str, Any], *, expected_version: int) -> dict:
        return await self._write(identifier, self._fields(values), expected_version)

    async def soft_delete(self, identifier: UUID, *, expected_version: int) -> dict:
        return await self._write(identifier, {
            "deleted_at": func.clock_timestamp(), "deleted_by": self.scope.actor_id,
        }, expected_version)

    async def _write(self, identifier: UUID, fields: dict, expected_version: int) -> dict:
        if type(expected_version) is not int or expected_version < 1:
            raise ValueError("Positive expected_version required")
        await self._authorize()
        row = (await self.session.execute(update(self.table).where(
            *self._visible(), self.table.c.kitchen_id == identifier,
            self.table.c.version == expected_version,
        ).values(**fields, updated_by=self.scope.actor_id, updated_at=func.clock_timestamp(),
                 version=self.table.c.version + 1).returning(self.table))).mappings().one_or_none()
        if row is None:
            # Re-check visibility without revealing records outside this tenant.
            await self.get(identifier)
            raise VersionConflictError("Kitchen changed; reload before retrying")
        await sync_source(self.session, self.scope, 'KITCHEN', identifier)
        return dict(row)
