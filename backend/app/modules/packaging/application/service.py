from datetime import UTC, datetime, timedelta
from math import floor
from uuid import UUID, uuid4

from sqlalchemy import func, insert, select, update

from app.core.database.scope import RecordNotFoundError, VersionConflictError
from app.core.events.orm import EventLog
from app.modules.authentication.infrastructure.authorization import require_permission
from app.modules.master.infrastructure.orm import HoldingRule, Kitchen, PackagingType
from app.modules.packaging.schemas.packages import HoldingPolicy, PackageData
from app.modules.production.infrastructure.orm import Package, ProductionBatch
from app.modules.receiving.application.service import ReceivingService
from app.modules.telemetry.infrastructure.orm import HoldingLog
from app.modules.traceability.infrastructure.orm import AssetMovement, AssetRelationship
from app.modules.traceability.infrastructure.registry import sync_source


def timer(production, package, now):
    policy = production['holding_policy']
    if policy is None or package['expired_at'] is None or production['finished_at'] is None:
        return {'remaining_seconds': None, 'remaining_minutes': None, 'timer_status': 'UNKNOWN',
                'effective_status': package['status'], 'holding_eligible': False}
    seconds = floor((package['expired_at'] - now).total_seconds())
    elapsed = (now - production['finished_at']).total_seconds()
    state = ('DISCARD_RECOMMENDED' if elapsed >= policy['discard_minutes'] * 60 else
             'EXPIRED' if seconds <= 0 else 'WARNING' if seconds <= policy['warning_minutes'] * 60 else 'SAFE')
    effective = package['status'] if package['status'] in ('DISCARDED', 'REJECTED', 'CONSUMED') else (
        'EXPIRED' if state in ('EXPIRED', 'DISCARD_RECOMMENDED') else package['status'])
    return {'remaining_seconds': seconds, 'remaining_minutes': floor(seconds / 60), 'timer_status': state,
            'effective_status': effective,
            'holding_eligible': effective == 'RELEASED' and state in ('SAFE', 'WARNING')}


class PackagingConflictError(Exception):
    pass


class PackageService(ReceivingService):
    async def projection(self, package, now=None):
        production = await self.row(ProductionBatch, 'production_batch_id', package['production_batch_id'])
        now = now or datetime.now(UTC)
        return {**package, **timer(production, package, now), 'calculated_at': now,
                'uom': (production['recipe_snapshot'] or {}).get('uom'),
                'holding_policy': production['holding_policy'],
                'qr_payload': f"fsos:package:{package['package_id']}"}

    async def get(self, identifier):
        await require_permission(self.db, self.scope, 'Package.Read')
        return await self.projection(await self.row(Package, 'package_id', identifier))

    async def resolve(self, payload):
        await require_permission(self.db, self.scope, 'Package.Read')
        try:
            if not payload.startswith('fsos:package:'):
                raise ValueError()
            identifier = UUID(payload.removeprefix('fsos:package:'))
        except ValueError:
            raise PackagingConflictError('Invalid package QR payload') from None
        return await self.projection(await self.row(Package, 'package_id', identifier))

    async def list(self, *, offset=0, limit=20, production_batch_id=None):
        await require_permission(self.db, self.scope, 'Package.Read')
        query = select(Package.__table__).where(*self.visible(Package))
        if production_batch_id is not None:
            query = query.where(Package.production_batch_id == production_batch_id)
        rows = (await self.db.execute(query.order_by(Package.created_at.desc(), Package.package_id.desc())
            .offset(offset).limit(limit + 1))).mappings().all()
        now = datetime.now(UTC)
        return {'items': [await self.projection(dict(r), now) for r in rows[:limit]],
                'offset': offset, 'limit': limit, 'next_offset': offset + limit if len(rows) > limit else None}

    async def allocation(self, identifier):
        await require_permission(self.db, self.scope, 'Package.Read')
        production = await self.row(ProductionBatch, 'production_batch_id', identifier, lock=True)
        allocated = await self.allocated(identifier)
        unknown = await self.db.scalar(select(Package.package_id).where(*self.visible(Package),
            Package.production_batch_id == identifier, Package.quantity.is_(None)).limit(1))
        return {'production_batch_id': identifier, 'version': production['version'],
                'actual_quantity': production['actual_quantity'], 'allocated_quantity': allocated,
                'unallocated_quantity': None if production['actual_quantity'] is None or unknown is not None else production['actual_quantity'] - allocated,
                'uom': (production['recipe_snapshot'] or {}).get('uom'), 'holding_policy': production['holding_policy']}

    async def allocated(self, identifier):
        return await self.db.scalar(select(func.coalesce(func.sum(Package.quantity), 0)).where(
            *self.visible(Package), Package.production_batch_id == identifier))

    async def policy(self, production):
        if production['holding_policy'] is not None:
            return production['holding_policy']
        food = production['recipe_snapshot'] or {}
        category, cap = food.get('food_category'), food.get('holding_limit_minutes')
        rule = None
        if category is not None:
            rule = (await self.db.execute(select(HoldingRule.__table__).where(*self.visible(HoldingRule),
                HoldingRule.food_category == category).with_for_update(read=True))).mappings().one_or_none()
        maximum = min(cap, rule['maximum_minutes']) if cap is not None and rule else cap if cap is not None else rule['maximum_minutes'] if rule else None
        if maximum is None or maximum <= 0:
            raise PackagingConflictError('Positive holding policy from production snapshot or category rule required')
        warning = min(rule['warning_minutes'], maximum) if rule else 0
        discard = min(rule['discard_minutes'], cap) if rule and cap is not None else rule['discard_minutes'] if rule else maximum
        return HoldingPolicy(schema_version=1, rule_id=rule['holding_rule_id'] if rule else None,
            rule_version=rule['version'] if rule else None, food_category=category, maximum_minutes=maximum,
            warning_minutes=warning, discard_minutes=discard).model_dump(mode='json')

    async def create(self, payload):
        await require_permission(self.db, self.scope, 'Package.Write')
        initial = await self.row(ProductionBatch, 'production_batch_id', payload.production_batch_id)
        try:
            kitchen = await self.row(Kitchen, 'kitchen_id', initial['kitchen'], lock=True)
            await self.row(PackagingType, 'package_type_id', payload.package_type_id, lock=True)
        except RecordNotFoundError:
            raise PackagingConflictError('Kitchen and packaging type in this tenant required') from None
        if kitchen['status'] != 'ACTIVE':
            raise PackagingConflictError('Active kitchen required')
        production = await self.row(ProductionBatch, 'production_batch_id', payload.production_batch_id, lock=True)
        if production['version'] != payload.expected_version:
            raise VersionConflictError()
        if production['status'] != 'COMPLETED' or production['actual_quantity'] is None or production['finished_at'] is None:
            raise PackagingConflictError('Completed production with actual yield required')
        # Unknown legacy quantities make safe allocation impossible.
        legacy = await self.db.scalar(select(Package.package_id).where(*self.visible(Package),
            Package.production_batch_id == payload.production_batch_id, Package.quantity.is_(None)).limit(1))
        if legacy is not None:
            raise PackagingConflictError('Legacy packages require quantity reconciliation')
        if payload.quantity > production['actual_quantity'] - await self.allocated(payload.production_batch_id):
            raise PackagingConflictError('Package quantity exceeds unallocated production yield')
        policy = await self.policy(production)
        expiry = production['finished_at'] + timedelta(minutes=policy['maximum_minutes'])
        now = datetime.now(UTC)
        if now >= expiry:
            raise PackagingConflictError('Production holding time has expired')
        await self.db.execute(update(ProductionBatch).where(*self.visible(ProductionBatch),
            ProductionBatch.production_batch_id == payload.production_batch_id).values(
                holding_policy=policy, holding_started_at=production['finished_at'], holding_expired_at=expiry,
                version=production['version'] + 1, updated_at=now, updated_by=self.scope.actor_id))
        identifier = uuid4()
        await self.db.execute(insert(Package).values(package_id=identifier,
            **payload.model_dump(exclude={'expected_version'}), expired_at=expiry,
            remaining_minutes=floor((expiry - now).total_seconds() / 60), status='CREATED', **self.audit))
        package_asset = await sync_source(self.db, self.scope, 'PACKAGE', identifier)
        production_asset = await sync_source(self.db, self.scope, 'PRODUCTION_BATCH', payload.production_batch_id)
        location = await sync_source(self.db, self.scope, 'KITCHEN', production['kitchen'])
        await self.db.execute(insert(AssetRelationship).values(relationship_uuid=uuid4(),
            parent_uuid=production_asset['asset_uuid'], child_uuid=package_asset['asset_uuid'], relationship_type='PACKAGED', **self.audit))
        await self.db.execute(insert(AssetMovement).values(movement_id=uuid4(), asset_type='PACKAGE', asset_uuid=package_asset['asset_uuid'],
            movement_type='PACKAGING', from_location=None, to_location=location['asset_uuid'], operator=self.scope.actor_id,
            movement_time=now, remarks=None, **self.audit))
        result = await self.projection(await self.row(Package, 'package_id', identifier), now)
        await self.event('package.created', result)
        return result

    async def holding(self, identifier, payload, action):
        await require_permission(self.db, self.scope, {'start': 'Holding.Start', 'update': 'Holding.Update', 'finish': 'Holding.Finish'}[action])
        package = await self.row(Package, 'package_id', identifier, lock=True)
        if package['version'] != payload.expected_version:
            raise VersionConflictError()
        now = datetime.now(UTC)
        result = await self.projection(package, now)
        if result['holding_policy'] is None or package['quantity'] is None:
            raise PackagingConflictError('Legacy package has no executable holding policy')
        if package['status'] == 'DISCARDED':
            raise PackagingConflictError('Discarded package is final')
        if package['status'] not in {'CREATED', 'PACKAGED', 'RELEASED', 'EXPIRED'}:
            raise PackagingConflictError('Package is managed by delivery or downstream workflow')
        expired = result['timer_status'] in ('EXPIRED', 'DISCARD_RECOMMENDED')
        values = {}
        if action == 'start':
            if package['status'] != 'CREATED' or package['holding_started_at'] is not None or expired:
                raise PackagingConflictError('Only unexpired CREATED package can start holding')
            production = await self.row(ProductionBatch, 'production_batch_id', package['production_batch_id'])
            values.update(status='PACKAGED', holding_started_at=production['finished_at'])
        elif action == 'finish':
            if payload.outcome == 'RELEASED' and (package['status'] != 'PACKAGED' or expired):
                raise PackagingConflictError('Only unexpired PACKAGED package can be released')
            values.update(status=payload.outcome, holding_finished_at=now)
        else:
            # Refresh materializes expiry without extending/resetting the deadline.
            values['status'] = 'EXPIRED' if expired else package['status']
        values.update(remaining_minutes=result['remaining_minutes'], version=package['version'] + 1,
                      updated_at=now, updated_by=self.scope.actor_id)
        await self.db.execute(update(Package).where(*self.visible(Package), Package.package_id == identifier).values(**values))
        await sync_source(self.db, self.scope, 'PACKAGE', identifier)
        result = await self.projection(await self.row(Package, 'package_id', identifier), now)
        production = await self.row(ProductionBatch, 'production_batch_id', package['production_batch_id'])
        await self.db.execute(insert(HoldingLog).values(holding_id=uuid4(), package_uuid=identifier, recorded_at=now,
            elapsed_minutes=max(0, floor((now - production['finished_at']).total_seconds() / 60)),
            remaining_minutes=result['remaining_minutes'], status=result['effective_status'], warning_level=result['timer_status'], **self.audit))
        event = 'holding.started' if action == 'start' else 'holding.finished' if action == 'finish' else 'holding.expired' if expired and package['status'] != 'EXPIRED' else 'holding.updated'
        await self.event(event, result)
        return result

    async def event(self, name, package):
        await self.db.execute(insert(EventLog).values(event_uuid=uuid4(), event_type=name, entity_type='PACKAGE',
            entity_uuid=package['package_id'], payload={'schema_version': 1, 'actor_id': str(self.scope.actor_id),
            'package': PackageData.model_validate(package).model_dump(mode='json')}, **self.audit))
