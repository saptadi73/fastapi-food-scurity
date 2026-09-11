from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.scope import ActorScope
from app.modules.authentication.infrastructure.authorization import require_permission
from app.modules.traceability.infrastructure.registry import (
    inspect_registry,
    source_adapter,
    sync_source,
)


class RegistryService:
    def __init__(self, session: AsyncSession, scope: ActorScope):
        self.session, self.scope = session, scope

    async def sync(self, asset_type: str, entity_id: UUID) -> dict:
        await require_permission(self.session, self.scope, 'AssetRegistry.Sync')
        return await sync_source(self.session, self.scope, asset_type, entity_id)

    async def reconcile(self, asset_type: str, *, after_id: UUID | None = None, limit: int = 100) -> dict:
        """Report missing sources and projection drift without modifying traceability evidence."""
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError('limit must be between 1 and 200')
        if after_id is not None and not isinstance(after_id, UUID):
            raise ValueError('after_id must be a UUID')
        await require_permission(self.session, self.scope, 'AssetRegistry.Sync')
        return await inspect_registry(self.session, self.scope, asset_type, after_id=after_id, limit=limit)

    async def backfill(self, asset_type: str, *, after_id: UUID | None = None, limit: int = 100) -> dict:
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError('limit must be between 1 and 200')
        await require_permission(self.session, self.scope, 'AssetRegistry.Sync')
        adapter = source_adapter(asset_type)
        table = adapter.model.__table__
        key = table.c[adapter.key]
        query = select(key).where(table.c.tenant_id == self.scope.tenant_id).order_by(key).limit(limit)
        if after_id is not None:
            query = query.where(key > after_id)
        ids = (await self.session.execute(query)).scalars().all()
        for identifier in ids:
            await sync_source(self.session, self.scope, asset_type, identifier)
        return {'processed': len(ids), 'last_id': ids[-1] if ids else None}
