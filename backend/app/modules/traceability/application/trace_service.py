from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.scope import ActorScope, RecordNotFoundError
from app.modules.authentication.infrastructure.authorization import require_permission
from app.modules.traceability.infrastructure.orm import AssetMovement, AssetRelationship, DigitalAsset


class TraceabilityService:
    def __init__(self, session: AsyncSession, scope: ActorScope):
        self.session, self.scope = session, scope

    def visible(self, model):
        return model.tenant_id == self.scope.tenant_id, model.deleted_at.is_(None)

    async def asset(self, asset_uuid):
        await require_permission(self.session, self.scope, 'Traceability.Read')
        row = (await self.session.execute(select(DigitalAsset.__table__).where(
            *self.visible(DigitalAsset),
            DigitalAsset.asset_uuid == asset_uuid,
        ))).mappings().one_or_none()
        if row is None:
            raise RecordNotFoundError()
        return dict(row)

    async def relationships(self, asset_uuid, *, direction, offset=0, limit=20):
        await self.asset(asset_uuid)
        column = AssetRelationship.parent_uuid if direction == 'children' else AssetRelationship.child_uuid
        query = select(AssetRelationship.__table__).where(*self.visible(AssetRelationship), column == asset_uuid)
        rows = (await self.session.execute(query.order_by(
            AssetRelationship.created_at.desc(),
            AssetRelationship.relationship_uuid.desc(),
        ).offset(offset).limit(limit + 1))).mappings().all()
        return {'items': [dict(row) for row in rows[:limit]], 'offset': offset, 'limit': limit,
                'next_offset': offset + limit if len(rows) > limit else None}

    async def movements(self, asset_uuid, *, offset=0, limit=20):
        await self.asset(asset_uuid)
        rows = (await self.session.execute(select(AssetMovement.__table__).where(
            *self.visible(AssetMovement),
            AssetMovement.asset_uuid == asset_uuid,
        ).order_by(
            AssetMovement.movement_time.desc(),
            AssetMovement.movement_id.desc(),
        ).offset(offset).limit(limit + 1))).mappings().all()
        return {'items': [dict(row) for row in rows[:limit]], 'offset': offset, 'limit': limit,
                'next_offset': offset + limit if len(rows) > limit else None}

    async def traverse(self, asset_uuid, *, direction, depth=3, limit=100):
        root = await self.asset(asset_uuid)
        if depth < 1 or depth > 6 or limit < 1 or limit > 200:
            raise ValueError('Invalid traversal bounds')
        nodes = {root['asset_uuid']: root}
        edges = {}
        frontier = {root['asset_uuid']}
        truncated = False
        for _ in range(depth):
            if not frontier or len(nodes) >= limit:
                break
            if direction == 'forward':
                source_column = AssetRelationship.parent_uuid
                target_column = AssetRelationship.child_uuid
            else:
                source_column = AssetRelationship.child_uuid
                target_column = AssetRelationship.parent_uuid
            rows = (await self.session.execute(select(AssetRelationship.__table__).where(
                *self.visible(AssetRelationship),
                source_column.in_(frontier),
            ).order_by(AssetRelationship.created_at, AssetRelationship.relationship_uuid))).mappings().all()
            next_frontier = set()
            for row in rows:
                edge = dict(row)
                edges[edge['relationship_uuid']] = edge
                next_frontier.add(edge[target_column.key])
            missing = next_frontier - set(nodes)
            added = set()
            if missing:
                asset_rows = (await self.session.execute(select(DigitalAsset.__table__).where(
                    *self.visible(DigitalAsset),
                    DigitalAsset.asset_uuid.in_(missing),
                ))).mappings().all()
                for row in asset_rows:
                    if len(nodes) >= limit:
                        truncated = True
                        break
                    nodes[row['asset_uuid']] = dict(row)
                    added.add(row['asset_uuid'])
            frontier = added
        return {'root_asset_uuid': asset_uuid, 'direction': direction, 'depth': depth,
                'nodes': list(nodes.values()), 'edges': list(edges.values()), 'truncated': truncated}

    async def passport(self, asset_uuid):
        asset = await self.asset(asset_uuid)
        parents = await self.relationships(asset_uuid, direction='parents', offset=0, limit=100)
        children = await self.relationships(asset_uuid, direction='children', offset=0, limit=100)
        movements = await self.movements(asset_uuid, offset=0, limit=100)
        return {
            'asset': asset,
            'parents': parents['items'],
            'children': children['items'],
            'movements': movements['items'],
        }

    async def impact(self, asset_uuid, *, depth=6, limit=200):
        graph = await self.traverse(asset_uuid, direction='forward', depth=depth, limit=limit)
        impacted = [node for node in graph['nodes'] if node['asset_uuid'] != asset_uuid]
        counts = {}
        for node in impacted:
            counts[node['asset_type']] = counts.get(node['asset_type'], 0) + 1
        return {
            'root_asset_uuid': asset_uuid,
            'depth': depth,
            'impacted_assets': impacted,
            'affected_counts': counts,
            'package_assets': [node for node in impacted if node['asset_type'] == 'PACKAGE'],
            'complaint_assets': [node for node in impacted if node['asset_type'] == 'COMPLAINT'],
            'recall_assets': [node for node in impacted if node['asset_type'] == 'RECALL'],
            'edges': graph['edges'],
            'truncated': graph['truncated'],
        }
