from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import insert, select

from app.core.database.scope import RecordNotFoundError
from app.core.events.orm import EventLog
from app.modules.authentication.infrastructure.authorization import require_permission
from app.modules.complaint.infrastructure.orm import Complaint
from app.modules.complaint.schemas import ComplaintData
from app.modules.consumption.infrastructure.orm import Consumption
from app.modules.fleet.infrastructure.orm import Delivery, DeliveryItem, SchoolReceiving
from app.modules.master.infrastructure.orm import School
from app.modules.production.infrastructure.orm import Package, ProductionBatch, ProductionItem
from app.modules.receiving.application.service import ReceivingService
from app.modules.receiving.infrastructure.orm import RawMaterialBatch, Receiving, ReceivingItem, StockIssue
from app.modules.traceability.infrastructure.orm import AssetMovement, AssetRelationship, DigitalAsset
from app.modules.traceability.infrastructure.registry import sync_source


class ComplaintConflictError(Exception):
    pass


class ComplaintService(ReceivingService):
    async def get(self, identifier):
        await require_permission(self.db, self.scope, 'Complaint.Read')
        return await self.row(Complaint, 'complaint_id', identifier)

    async def list(self, *, offset=0, limit=20, package_id=None, school_id=None):
        await require_permission(self.db, self.scope, 'Complaint.Read')
        query = select(Complaint.__table__).where(*self.visible(Complaint))
        if package_id is not None:
            query = query.where(Complaint.package_id == package_id)
        if school_id is not None:
            query = query.where(Complaint.school_id == school_id)
        rows = (await self.db.execute(query.order_by(Complaint.created_at.desc(), Complaint.complaint_id.desc())
            .offset(offset).limit(limit + 1))).mappings().all()
        return {'items': [dict(r) for r in rows[:limit]], 'offset': offset, 'limit': limit,
                'next_offset': offset + limit if len(rows) > limit else None}

    async def report(self, identifier):
        await require_permission(self.db, self.scope, 'Complaint.Read')
        complaint = await self.row(Complaint, 'complaint_id', identifier)
        package = await self.row(Package, 'package_id', complaint['package_id'])
        production = (await self.db.execute(select(ProductionBatch.__table__).where(
            *self.visible(ProductionBatch),
            ProductionBatch.production_batch_id == package['production_batch_id'],
        ))).mappings().one_or_none()
        manifest = (await self.db.execute(select(
            DeliveryItem.__table__,
            Delivery.__table__.c.status.label('delivery_status'),
            Delivery.__table__.c.vehicle.label('vehicle_id'),
            Delivery.__table__.c.driver.label('driver_id'),
            Delivery.__table__.c.departure_time,
            Delivery.__table__.c.arrival_time,
            Delivery.__table__.c.estimated_arrival_time,
            School.__table__.c.school_name,
        ).join(Delivery, (Delivery.tenant_id == DeliveryItem.tenant_id)
            & (Delivery.delivery_id == DeliveryItem.delivery_id))
            .join(School, (School.tenant_id == DeliveryItem.tenant_id)
                  & (School.school_id == DeliveryItem.school_id))
            .where(*self.visible(DeliveryItem), *self.visible(Delivery), *self.visible(School),
                   DeliveryItem.package_id == package['package_id'])
            .order_by(Delivery.created_at.desc(), Delivery.delivery_id.desc()))).mappings().all()
        receipts = (await self.db.execute(select(
            SchoolReceiving.__table__,
            Delivery.__table__.c.status.label('delivery_status'),
        ).join(Delivery, (Delivery.tenant_id == SchoolReceiving.tenant_id)
            & (Delivery.delivery_id == SchoolReceiving.delivery_id))
            .where(*self.visible(SchoolReceiving), *self.visible(Delivery),
                   SchoolReceiving.package == package['package_id'])
            .order_by(SchoolReceiving.received_time.desc()))).mappings().all()
        consumption = (await self.db.execute(select(Consumption.__table__).where(
            *self.visible(Consumption), Consumption.package_id == package['package_id'],
        ))).mappings().one_or_none()
        materials = []
        if production is not None:
            rows = (await self.db.execute(select(
                ProductionItem.__table__,
                RawMaterialBatch.__table__.c.batch_code,
                RawMaterialBatch.__table__.c.expired_date,
                RawMaterialBatch.__table__.c.status.label('raw_batch_status'),
                Receiving.__table__.c.received_at,
                ReceivingItem.__table__.c.temperature.label('receiving_temperature'),
                ReceivingItem.__table__.c.condition.label('receiving_condition'),
                ReceivingItem.__table__.c.photo.label('receiving_photo'),
            ).join(RawMaterialBatch, (RawMaterialBatch.tenant_id == ProductionItem.tenant_id)
                & (RawMaterialBatch.raw_material_batch_id == ProductionItem.raw_material_batch_id))
                .join(ReceivingItem, (ReceivingItem.tenant_id == ProductionItem.tenant_id)
                      & (ReceivingItem.raw_material_batch_id == ProductionItem.raw_material_batch_id))
                .join(Receiving, (Receiving.tenant_id == RawMaterialBatch.tenant_id)
                      & (Receiving.receiving_id == RawMaterialBatch.receiving_id))
                .where(*self.visible(ProductionItem), *self.visible(RawMaterialBatch),
                       *self.visible(ReceivingItem), *self.visible(Receiving),
                       ProductionItem.production_batch_id == production['production_batch_id'])
                .order_by(RawMaterialBatch.expired_date, RawMaterialBatch.batch_code))).mappings().all()
            for row in rows:
                issues = (await self.db.execute(select(StockIssue.__table__).where(
                    *self.visible(StockIssue),
                    StockIssue.raw_material_batch_id == row['raw_material_batch_id'],
                ).order_by(StockIssue.issued_at.desc()))).mappings().all()
                materials.append({**dict(row), 'manual_issues': [dict(issue) for issue in issues]})
        package_asset = (await self.db.execute(select(DigitalAsset.__table__).where(
            *self.visible(DigitalAsset),
            DigitalAsset.asset_type == 'PACKAGE',
            DigitalAsset.entity_uuid == package['package_id'],
        ))).mappings().one_or_none()
        complaint_asset = (await self.db.execute(select(DigitalAsset.__table__).where(
            *self.visible(DigitalAsset),
            DigitalAsset.asset_type == 'COMPLAINT',
            DigitalAsset.entity_uuid == complaint['complaint_id'],
        ))).mappings().one_or_none()
        movements = []
        if package_asset is not None:
            movements = [dict(row) for row in (await self.db.execute(select(AssetMovement.__table__).where(
                *self.visible(AssetMovement),
                AssetMovement.asset_uuid == package_asset['asset_uuid'],
            ).order_by(AssetMovement.movement_time.desc()).limit(100))).mappings().all()]
        location = None
        if receipts:
            location = {'type': 'SCHOOL', 'school_id': receipts[0]['school'], 'detected_at': receipts[0]['received_time'],
                        'status': 'RECEIVED' if receipts[0]['accepted'] else 'REJECTED'}
        elif manifest:
            location = {'type': 'DELIVERY', 'delivery_id': manifest[0]['delivery_id'],
                        'vehicle_id': manifest[0]['vehicle_id'], 'status': manifest[0]['delivery_status']}
        return {**complaint, 'package': dict(package), 'production_batch': None if production is None else dict(production),
                'current_location': location, 'delivery_manifest': [dict(row) for row in manifest],
                'school_receivings': [dict(row) for row in receipts],
                'consumption': None if consumption is None else dict(consumption),
                'raw_materials': materials,
                'traceability': {
                    'package_asset_uuid': None if package_asset is None else package_asset['asset_uuid'],
                    'complaint_asset_uuid': None if complaint_asset is None else complaint_asset['asset_uuid'],
                    'package_movements': movements,
                }}

    async def reports(self, *, offset=0, limit=20, package_id=None, school_id=None):
        await require_permission(self.db, self.scope, 'Complaint.Read')
        query = select(Complaint.__table__).where(*self.visible(Complaint))
        if package_id is not None:
            query = query.where(Complaint.package_id == package_id)
        if school_id is not None:
            query = query.where(Complaint.school_id == school_id)
        rows = (await self.db.execute(query.order_by(Complaint.created_at.desc(), Complaint.complaint_id.desc())
            .offset(offset).limit(limit + 1))).mappings().all()
        return {'items': [await self.report(row['complaint_id']) for row in rows[:limit]],
                'offset': offset, 'limit': limit, 'next_offset': offset + limit if len(rows) > limit else None}

    async def create(self, payload):
        await require_permission(self.db, self.scope, 'Complaint.Write')
        try:
            if payload.package_id is not None:
                package = await self.row(Package, 'package_id', payload.package_id, lock=True)
            else:
                package = (await self.db.execute(select(Package.__table__).where(
                    *self.visible(Package),
                    Package.package_code == payload.package_code,
                ).with_for_update())).mappings().one_or_none()
                if package is None:
                    raise RecordNotFoundError()
            school = await self.row(School, 'school_id', payload.school_id, lock=True)
        except RecordNotFoundError:
            raise ComplaintConflictError('Package and school in this tenant required') from None
        if school['status'] != 'ACTIVE':
            raise ComplaintConflictError('Active school required')
        manifest = await self.db.scalar(select(DeliveryItem.delivery_item_id).join(
            Delivery,
            (Delivery.tenant_id == DeliveryItem.tenant_id)
            & (Delivery.delivery_id == DeliveryItem.delivery_id),
        ).where(
            *self.visible(DeliveryItem), *self.visible(Delivery),
            DeliveryItem.package_id == package['package_id'],
            DeliveryItem.school_id == payload.school_id,
            Delivery.status != 'CANCELLED',
        ).limit(1))
        if manifest is None:
            raise ComplaintConflictError('Package and school manifest required')
        now = datetime.now(UTC)
        identifier = uuid4()
        await self.db.execute(insert(Complaint).values(
            complaint_id=identifier,
            reported_at=now,
            package_id=package['package_id'],
            school_id=payload.school_id,
            description=payload.description,
            photo=payload.photo,
            **self.audit,
        ))
        package_asset = await sync_source(self.db, self.scope, 'PACKAGE', package['package_id'])
        school_asset = await sync_source(self.db, self.scope, 'SCHOOL', school['school_id'])
        complaint_asset = await sync_source(self.db, self.scope, 'COMPLAINT', identifier)
        await self.db.execute(insert(AssetRelationship).values(
            relationship_uuid=uuid4(),
            parent_uuid=package_asset['asset_uuid'],
            child_uuid=complaint_asset['asset_uuid'],
            relationship_type='REPORTED',
            **self.audit,
        ))
        await self.db.execute(insert(AssetMovement).values(
            movement_id=uuid4(),
            asset_type='PACKAGE',
            asset_uuid=package_asset['asset_uuid'],
            movement_type='COMPLAINT',
            from_location=school_asset['asset_uuid'],
            to_location=None,
            operator=self.scope.actor_id,
            movement_time=now,
            remarks=str(identifier),
            **self.audit,
        ))
        result = await self.row(Complaint, 'complaint_id', identifier)
        await self.db.execute(insert(EventLog).values(
            event_uuid=uuid4(),
            event_type='complaint.recorded',
            entity_type='COMPLAINT',
            entity_uuid=identifier,
            payload={'schema_version': 1, 'actor_id': str(self.scope.actor_id),
                     'complaint': ComplaintData.model_validate(result).model_dump(mode='json')},
            **self.audit,
        ))
        return result
