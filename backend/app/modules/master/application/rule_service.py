from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.scope import ActorScope, RecordNotFoundError, VersionConflictError
from app.modules.authentication.infrastructure.authorization import require_permission
from app.modules.master.domain.rule_dsl import validate_rule_dsl
from app.modules.master.infrastructure.orm import (
    AlarmRule,
    AlarmRuleRevision,
    HoldingRule,
    HoldingRuleRevision,
)
from app.modules.master.schemas.rules import AlarmRuleInput, HoldingRuleInput


class RuleStateError(Exception):
    pass


class RuleService:
    """Caller owns transaction and verified identity. No HTTP or event publication."""

    def __init__(self, session: AsyncSession, scope: ActorScope, kind: str):
        if kind not in ('alarm', 'holding'):
            raise ValueError('Unsupported rule kind')
        self.session, self.scope, self.kind = session, scope, kind
        self.table = (AlarmRule if kind == 'alarm' else HoldingRule).__table__
        self.history_table = (AlarmRuleRevision if kind == 'alarm' else HoldingRuleRevision).__table__
        self.input_type = AlarmRuleInput if kind == 'alarm' else HoldingRuleInput
        self.prefix = 'AlarmRule' if kind == 'alarm' else 'HoldingRule'
        self.pk = self.table.c[f'{kind}_rule_id']

    async def _authorize(self, operation: str):
        await require_permission(self.session, self.scope, f'{self.prefix}.{operation}')

    def _visible(self, identifier: UUID):
        return (self.pk == identifier, self.table.c.tenant_id == self.scope.tenant_id,
                self.table.c.deleted_at.is_(None))

    async def _get(self, identifier: UUID, *, lock=False):
        query = select(self.table).where(*self._visible(identifier))
        if lock:
            query = query.with_for_update()
        row = (await self.session.execute(query)).mappings().one_or_none()
        if row is None:
            raise RecordNotFoundError('Rule not found')
        return dict(row)

    async def get(self, identifier: UUID) -> dict:
        await self._authorize('Read')
        return await self._get(identifier)

    async def list(self, *, offset: int = 0, limit: int = 20) -> list[dict]:
        if type(offset) is not int or type(limit) is not int or offset < 0 or not 1 <= limit <= 100:
            raise ValueError('Invalid rule pagination')
        await self._authorize('Read')
        rows = (await self.session.execute(select(self.table).where(
            self.table.c.tenant_id == self.scope.tenant_id, self.table.c.deleted_at.is_(None),
        ).order_by(self.table.c.created_at.desc(), self.pk.desc()).offset(offset).limit(limit))).mappings()
        return [dict(row) for row in rows]

    async def history(self, identifier: UUID, *, offset=0, limit=20) -> list[dict]:
        if type(offset) is not int or type(limit) is not int or offset < 0 or not 1 <= limit <= 100:
            raise ValueError('Invalid history pagination')
        await self._authorize('Read')
        await self._get(identifier)
        h = self.history_table
        rows = (await self.session.execute(select(h).where(
            h.c.tenant_id == self.scope.tenant_id, h.c.rule_id == identifier,
        ).order_by(h.c.version.desc()).offset(offset).limit(limit))).mappings()
        return [dict(row) for row in rows]

    async def create(self, values: dict) -> dict:
        await self._authorize('Write')
        data = self.input_type.model_validate(values).model_dump()
        if self.kind == 'alarm':
            data['enabled'] = False
        row = (await self.session.execute(insert(self.table).values(
            **data, **{self.pk.name: uuid4()}, tenant_id=self.scope.tenant_id,
            created_by=self.scope.actor_id, updated_by=self.scope.actor_id, version=1,
        ).returning(self.table))).mappings().one()
        return dict(row)

    @staticmethod
    def _check_version(row: dict, expected_version: int):
        if type(expected_version) is not int or expected_version < 1:
            raise ValueError('Positive expected_version required')
        if row['version'] != expected_version:
            raise VersionConflictError('Rule changed; reload before retrying')

    async def save(self, identifier: UUID, values: dict, *, expected_version: int) -> dict:
        await self._authorize('Write')
        row = await self._get(identifier, lock=True)
        self._check_version(row, expected_version)
        if self.kind == 'alarm' and row['enabled']:
            raise RuleStateError('Disable alarm rule before changing its definition')
        data = self.input_type.model_validate(values).model_dump()
        return await self._update(identifier, data, expected_version)

    async def set_enabled(self, identifier: UUID, enabled: bool, *, expected_version: int) -> dict:
        if self.kind != 'alarm' or type(enabled) is not bool:
            raise ValueError('Activation applies to alarm rules and requires a boolean')
        await self._authorize('Activate')
        row = await self._get(identifier, lock=True)
        self._check_version(row, expected_version)
        if enabled:
            # Revalidate persisted legacy rules; disable must remain possible even for invalid DSL.
            validate_rule_dsl(row['condition'], row['action'])
        if row['enabled'] == enabled:
            return row
        return await self._update(identifier, {'enabled': enabled}, expected_version)

    async def _update(self, identifier, data, expected_version):
        row = (await self.session.execute(update(self.table).where(
            *self._visible(identifier), self.table.c.version == expected_version,
        ).values(**data, updated_by=self.scope.actor_id).returning(self.table))).mappings().one_or_none()
        if row is None:
            raise VersionConflictError('Rule changed; reload before retrying')
        # Migration 0015 increments version and captures the revision in this transaction.
        return dict(row)
