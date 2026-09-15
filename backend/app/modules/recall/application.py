from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import insert, select, update

from app.core.database.scope import RecordNotFoundError, VersionConflictError
from app.core.events.orm import EventLog
from app.modules.authentication.infrastructure.authorization import require_permission
from app.modules.notification.application import enqueue_notification
from app.modules.production.infrastructure.orm import Package, ProductionBatch
from app.modules.receiving.application.service import ReceivingService
from app.modules.recall.infrastructure.orm import Recall, RecallWithdrawal
from app.modules.recall.schemas import RecallData, RecallWithdrawalData
from app.modules.traceability.infrastructure.orm import AssetMovement, AssetRelationship
from app.modules.traceability.infrastructure.registry import sync_source


class RecallConflictError(Exception):
    pass


class RecallService(ReceivingService):
    async def detail(self, identifier):
        recall = await self.row(Recall, 'recall_id', identifier)
        packages = (await self.db.execute(select(Package.__table__).where(
            *self.visible(Package),
            Package.production_batch_id == recall['production_batch_id'],
        ).order_by(Package.package_number, Package.package_id))).mappings().all()
        return {**recall, 'affected_packages': [dict(row) for row in packages]}

    async def get(self, identifier):
        await require_permission(self.db, self.scope, 'Recall.Read')
        return await self.detail(identifier)

    async def list(self, *, offset=0, limit=20, production_batch_id=None, open_only=None):
        await require_permission(self.db, self.scope, 'Recall.Read')
        query = select(Recall.__table__).where(*self.visible(Recall))
        if production_batch_id is not None:
            query = query.where(Recall.production_batch_id == production_batch_id)
        if open_only is True:
            query = query.where(Recall.completed_at.is_(None))
        elif open_only is False:
            query = query.where(Recall.completed_at.is_not(None))
        rows = (await self.db.execute(query.order_by(Recall.created_at.desc(), Recall.recall_id.desc())
            .offset(offset).limit(limit + 1))).mappings().all()
        items = [await self.detail(row['recall_id']) for row in rows[:limit]]
        return {'items': items, 'offset': offset, 'limit': limit,
                'next_offset': offset + limit if len(rows) > limit else None}

    async def create(self, payload):
        await require_permission(self.db, self.scope, 'Recall.Execute')
        try:
            production = await self.row(ProductionBatch, 'production_batch_id', payload.production_batch_id, lock=True)
        except RecordNotFoundError:
            raise RecallConflictError('Production batch in this tenant required') from None
        now = datetime.now(UTC)
        identifier = uuid4()
        await self.db.execute(insert(Recall).values(
            recall_id=identifier,
            started_at=now,
            completed_at=None,
            **payload.model_dump(),
            **self.audit,
        ))
        production_asset = await sync_source(self.db, self.scope, 'PRODUCTION_BATCH', production['production_batch_id'])
        recall_asset = await sync_source(self.db, self.scope, 'RECALL', identifier)
        await self.db.execute(insert(AssetRelationship).values(
            relationship_uuid=uuid4(),
            parent_uuid=production_asset['asset_uuid'],
            child_uuid=recall_asset['asset_uuid'],
            relationship_type='RECALLED',
            **self.audit,
        ))
        for package in (await self.db.execute(select(Package.__table__).where(
            *self.visible(Package),
            Package.production_batch_id == payload.production_batch_id,
        ).order_by(Package.package_id))).mappings():
            package_asset = await sync_source(self.db, self.scope, 'PACKAGE', package['package_id'])
            await self.db.execute(insert(AssetMovement).values(
                movement_id=uuid4(),
                asset_type='PACKAGE',
                asset_uuid=package_asset['asset_uuid'],
                movement_type='RECALL',
                from_location=None,
                to_location=None,
                operator=self.scope.actor_id,
                movement_time=now,
                remarks=str(identifier),
                **self.audit,
            ))
        result = await self.detail(identifier)
        await self.event('recall.started', result)
        return result

    async def close(self, identifier, payload):
        await require_permission(self.db, self.scope, 'Recall.Execute')
        current = await self.row(Recall, 'recall_id', identifier, lock=True)
        if current['version'] != payload.expected_version:
            raise VersionConflictError()
        if current['completed_at'] is not None:
            raise RecallConflictError('Recall already completed')
        now = datetime.now(UTC)
        await self.db.execute(update(Recall).where(
            *self.visible(Recall),
            Recall.recall_id == identifier,
        ).values(
            completed_at=now,
            updated_at=now,
            updated_by=self.scope.actor_id,
            version=Recall.version + 1,
        ))
        await sync_source(self.db, self.scope, 'RECALL', identifier)
        result = await self.detail(identifier)
        await self.event('recall.completed', result)
        return result

    async def execute(self, identifier, payload):
        await require_permission(self.db, self.scope, 'Recall.Execute')
        current = await self.row(Recall, 'recall_id', identifier, lock=True)
        if current['version'] != payload.expected_version:
            raise VersionConflictError()
        if current['completed_at'] is not None:
            raise RecallConflictError('Completed recall cannot be executed')
        now = datetime.now(UTC)
        recall_asset = await sync_source(self.db, self.scope, 'RECALL', identifier)
        packages = (await self.db.execute(select(Package.__table__).where(
            *self.visible(Package),
            Package.production_batch_id == current['production_batch_id'],
        ).with_for_update())).mappings().all()
        for package in packages:
            package_asset = await sync_source(self.db, self.scope, 'PACKAGE', package['package_id'])
            if package['status'] not in ('CONSUMED', 'DISCARDED', 'REJECTED', 'RECALLED'):
                await self.db.execute(update(Package).where(
                    *self.visible(Package),
                    Package.package_id == package['package_id'],
                ).values(
                    status='RECALLED',
                    updated_at=now,
                    updated_by=self.scope.actor_id,
                    version=Package.version + 1,
                ))
                package_asset = await sync_source(self.db, self.scope, 'PACKAGE', package['package_id'])
            await self.db.execute(insert(AssetRelationship).values(
                relationship_uuid=uuid4(),
                parent_uuid=package_asset['asset_uuid'],
                child_uuid=recall_asset['asset_uuid'],
                relationship_type='RECALLED',
                **self.audit,
            ))
            await self.db.execute(insert(AssetMovement).values(
                movement_id=uuid4(),
                asset_type='PACKAGE',
                asset_uuid=package_asset['asset_uuid'],
                movement_type='RECALL',
                from_location=None,
                to_location=None,
                operator=self.scope.actor_id,
                movement_time=now,
                remarks=str(identifier),
                **self.audit,
            ))
        await self.db.execute(update(Recall).where(
            *self.visible(Recall),
            Recall.recall_id == identifier,
        ).values(updated_at=now, updated_by=self.scope.actor_id, version=Recall.version + 1))
        result = await self.detail(identifier)
        await self.event('recall.executed', result)
        return result

    async def withdrawal(self, identifier, payload):
        await require_permission(self.db, self.scope, 'Recall.Execute')
        current = await self.row(Recall, 'recall_id', identifier, lock=True)
        if current['version'] != payload.expected_version:
            raise VersionConflictError()
        if current['completed_at'] is not None:
            raise RecallConflictError('Completed recall cannot receive withdrawal evidence')
        package = None
        if payload.package_id is not None:
            try:
                package = await self.row(Package, 'package_id', payload.package_id, lock=True)
            except RecordNotFoundError:
                raise RecallConflictError('Package in this recall required') from None
            if package['production_batch_id'] != current['production_batch_id']:
                raise RecallConflictError('Package in this recall required')
        now = datetime.now(UTC)
        withdrawn_at = payload.withdrawn_at or now
        identifier_withdrawal = uuid4()
        await self.db.execute(insert(RecallWithdrawal).values(
            withdrawal_id=identifier_withdrawal,
            recall_id=identifier,
            withdrawn_at=withdrawn_at,
            **payload.model_dump(exclude={'expected_version', 'withdrawn_at'}),
            **self.audit,
        ))
        asset_type = 'RECALL' if package is None else 'PACKAGE'
        asset_id = identifier if package is None else package['package_id']
        asset = await sync_source(self.db, self.scope, asset_type, asset_id)
        await self.db.execute(insert(AssetMovement).values(
            movement_id=uuid4(),
            asset_type=asset_type,
            asset_uuid=asset['asset_uuid'],
            movement_type='RECALL',
            from_location=None,
            to_location=None,
            operator=self.scope.actor_id,
            movement_time=withdrawn_at,
            remarks=f"withdrawal:{identifier_withdrawal};recall:{identifier};evidence:{payload.evidence_code}",
            **self.audit,
        ))
        await self.db.execute(update(Recall).where(
            *self.visible(Recall),
            Recall.recall_id == identifier,
        ).values(updated_at=now, updated_by=self.scope.actor_id, version=Recall.version + 1))
        withdrawal = await self.row(RecallWithdrawal, 'withdrawal_id', identifier_withdrawal)
        await self.event('recall.withdrawal_recorded', await self.detail(identifier),
                         withdrawal=RecallWithdrawalData.model_validate(withdrawal).model_dump(mode='json'))
        return withdrawal

    async def withdrawals(self, identifier, *, offset=0, limit=20, package_id=None):
        await require_permission(self.db, self.scope, 'Recall.Read')
        await self.row(Recall, 'recall_id', identifier)
        query = select(RecallWithdrawal.__table__).where(
            *self.visible(RecallWithdrawal),
            RecallWithdrawal.recall_id == identifier,
        )
        if package_id is not None:
            query = query.where(RecallWithdrawal.package_id == package_id)
        rows = (await self.db.execute(query.order_by(
            RecallWithdrawal.withdrawn_at.desc(),
            RecallWithdrawal.withdrawal_id.desc(),
        ).offset(offset).limit(limit + 1))).mappings().all()
        return {'items': [dict(row) for row in rows[:limit]], 'offset': offset, 'limit': limit,
                'next_offset': offset + limit if len(rows) > limit else None}

    async def event(self, name, recall, **extra):
        event_payload = {'schema_version': 1, 'actor_id': str(self.scope.actor_id),
                         'recall': RecallData.model_validate(recall).model_dump(mode='json')}
        event_payload.update(extra)
        await self.db.execute(insert(EventLog).values(
            event_uuid=uuid4(),
            event_type=name,
            entity_type='RECALL',
            entity_uuid=recall['recall_id'],
            payload=event_payload,
            **self.audit,
        ))
        await enqueue_notification(
            self.db,
            self.scope,
            event_type=name,
            entity_type='RECALL',
            entity_uuid=recall['recall_id'],
            subject=f"Recall {name.removeprefix('recall.')}",
            message=f"Recall {recall['recall_id']} {name} for production batch {recall['production_batch_id']}.",
        )
