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
from app.modules.recall.infrastructure.orm import Recall
from app.modules.signature.infrastructure import SignatureEvidence
from app.modules.traceability.infrastructure.orm import AssetMovement, AssetRelationship, DigitalAsset
from app.modules.traceability.infrastructure.registry import sync_source


class ComplaintConflictError(Exception):
    pass


class ComplaintService(ReceivingService):
    async def package_alerts(self, package_id):
        await require_permission(self.db, self.scope, 'Complaint.Read')
        package = await self.row(Package, 'package_id', package_id)
        complaint_package = Package.__table__.alias('complaint_package')
        rows = (await self.db.execute(select(
            Complaint.complaint_id, Complaint.category, Complaint.severity, Complaint.status,
            Complaint.description, Complaint.reported_at, Complaint.package_id.label('source_package_id'),
        ).join(complaint_package,
            (complaint_package.c.tenant_id == Complaint.tenant_id)
            & (complaint_package.c.package_id == Complaint.package_id)).where(
            Complaint.tenant_id == self.scope.tenant_id, Complaint.deleted_at.is_(None),
            Complaint.status.in_(['OPEN', 'INVESTIGATING']),
            complaint_package.c.production_batch_id == package['production_batch_id'],
        ).order_by(Complaint.reported_at.desc()))).mappings().all()
        production = await self.row(ProductionBatch, 'production_batch_id', package['production_batch_id'])
        impact = await self.batch_impact(rows[0]['complaint_id']) if rows else None
        impacted_packages = [] if impact is None else impact['packages']
        recall = (await self.db.execute(select(Recall.__table__).where(
            *self.visible(Recall), Recall.production_batch_id == package['production_batch_id'],
        ).order_by(Recall.started_at.desc(), Recall.recall_id.desc()).limit(1))).mappings().one_or_none()
        recalled_count = sum(row['package_status'] == 'RECALLED' for row in impacted_packages)
        recall_status = ('NONE' if recall is None else
                         'COMPLETED' if recall['completed_at'] is not None else
                         'EXECUTED' if recalled_count else 'OPEN')
        actions = []
        if rows:
            actions = [
                {'code': 'HOLD_RECEIVING_CONSUMPTION',
                 'label': 'Tahan penerimaan dan konsumsi sampai investigasi dinyatakan aman.',
                 'required': True},
                {'code': 'ISOLATE_PACKAGE',
                 'label': 'Pisahkan kemasan terdampak dan jangan distribusikan kembali.',
                 'required': True},
                {'code': 'OPEN_BATCH_IMPACT',
                 'label': 'Buka laporan dampak batch untuk memeriksa semua tujuan dan penerima.',
                 'required': True},
            ]
            if recall is not None:
                actions.append({'code': 'FOLLOW_RECALL',
                                'label': 'Ikuti instruksi recall dan catat penarikan fisik kemasan.',
                                'required': True})
        return {
            'package_id': package_id,
            'production_batch_id': package['production_batch_id'],
            'production_batch_code': production['batch_code'],
            'has_active_incident': bool(rows),
            'highest_severity': self.highest_severity(rows),
            'primary_complaint_id': None if not rows else rows[0]['complaint_id'],
            'alerts': [dict(row) for row in rows],
            'affected_package_count': len(impacted_packages),
            'delivered_count': 0 if impact is None else impact['delivered_count'],
            'received_count': 0 if impact is None else impact['received_count'],
            'consumed_count': 0 if impact is None else impact['consumed_count'],
            'recalled_count': recalled_count,
            'recall_id': None if recall is None else recall['recall_id'],
            'recall_status': recall_status,
            'recall_reason': None if recall is None else recall['reason'],
            'recommended_actions': actions,
        }

    @staticmethod
    def highest_severity(rows):
        weights = {'LOW': 1, 'MEDIUM': 2, 'HIGH': 3, 'CRITICAL': 4}
        return max((row['severity'] for row in rows), key=lambda value: weights.get(value, 0), default=None)

    async def batch_impact(self, identifier):
        await require_permission(self.db, self.scope, 'Complaint.Read')
        complaint = await self.row(Complaint, 'complaint_id', identifier)
        source = await self.row(Package, 'package_id', complaint['package_id'])
        rows = (await self.db.execute(select(
            Package.package_id, Package.package_code, Package.status.label('package_status'), Package.quantity,
            Delivery.delivery_id, Delivery.status.label('delivery_status'), Delivery.departure_time,
            Delivery.arrival_time, DeliveryItem.school_id, School.school_code, School.school_name,
            SchoolReceiving.school_receiving_id, SchoolReceiving.received_time,
            SchoolReceiving.accepted, SchoolReceiving.condition,
            Consumption.consumption_id, Consumption.consumed_at, Consumption.consumed_quantity,
            Consumption.discarded_quantity,
        ).select_from(Package).outerjoin(DeliveryItem,
            (DeliveryItem.tenant_id == Package.tenant_id) & (DeliveryItem.package_id == Package.package_id)
        ).outerjoin(Delivery,
            (Delivery.tenant_id == DeliveryItem.tenant_id) & (Delivery.delivery_id == DeliveryItem.delivery_id)
        ).outerjoin(School,
            (School.tenant_id == DeliveryItem.tenant_id) & (School.school_id == DeliveryItem.school_id)
        ).outerjoin(SchoolReceiving,
            (SchoolReceiving.tenant_id == Package.tenant_id) & (SchoolReceiving.package == Package.package_id)
        ).outerjoin(Consumption,
            (Consumption.tenant_id == Package.tenant_id) & (Consumption.package_id == Package.package_id)
        ).where(Package.tenant_id == self.scope.tenant_id, Package.deleted_at.is_(None),
                Package.production_batch_id == source['production_batch_id'])
        .order_by(Package.package_number, Package.package_id))).mappings().all()
        packages = [dict(row) for row in rows]
        return {'complaint': dict(complaint), 'production_batch_id': source['production_batch_id'],
                'source_package_id': source['package_id'], 'affected_package_count': len(packages),
                'delivered_count': sum(row['delivery_id'] is not None for row in packages),
                'received_count': sum(row['school_receiving_id'] is not None for row in packages),
                'consumed_count': sum(row['consumption_id'] is not None for row in packages),
                'packages': packages}

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
            School.__table__.c.address.label('school_address'),
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
            School.__table__.c.school_name,
            School.__table__.c.address.label('school_address'),
        ).join(Delivery, (Delivery.tenant_id == SchoolReceiving.tenant_id)
            & (Delivery.delivery_id == SchoolReceiving.delivery_id))
            .join(School, (School.tenant_id == SchoolReceiving.tenant_id)
                  & (School.school_id == SchoolReceiving.school))
            .where(*self.visible(SchoolReceiving), *self.visible(Delivery), *self.visible(School),
                   SchoolReceiving.package == package['package_id'])
            .order_by(SchoolReceiving.received_time.desc()))).mappings().all()
        receipt_rows = []
        for row in receipts:
            signature = (await self.db.execute(select(
                SignatureEvidence.signature_id, SignatureEvidence.signed_by,
                SignatureEvidence.signed_at, SignatureEvidence.signer_snapshot,
            ).where(SignatureEvidence.tenant_id == self.scope.tenant_id,
                    SignatureEvidence.entity_type == 'SCHOOL_RECEIVING',
                    SignatureEvidence.entity_id == row['school_receiving_id'],
                    SignatureEvidence.deleted_at.is_(None),
            ).order_by(SignatureEvidence.signed_at.desc()).limit(1))).mappings().one_or_none()
            receipt_rows.append({**dict(row), 'received_by': None if signature is None else {
                'signature_id': signature['signature_id'], 'signed_by': signature['signed_by'],
                'signed_at': signature['signed_at'], 'signer_snapshot': signature['signer_snapshot']}})
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
        if receipt_rows:
            location = {'type': 'SCHOOL', 'school_id': receipts[0]['school'], 'school_name': receipts[0]['school_name'],
                        'school_address': receipts[0]['school_address'], 'detected_at': receipts[0]['received_time'],
                        'received_by': receipt_rows[0]['received_by'],
                        'status': 'RECEIVED' if receipts[0]['accepted'] else 'REJECTED'}
        elif manifest:
            location = {'type': 'DELIVERY', 'delivery_id': manifest[0]['delivery_id'],
                        'vehicle_id': manifest[0]['vehicle_id'], 'status': manifest[0]['delivery_status']}
        return {**complaint, 'package': dict(package), 'production_batch': None if production is None else dict(production),
                'current_location': location, 'delivery_manifest': [dict(row) for row in manifest],
                'school_receivings': receipt_rows,
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
            category=payload.category,
            severity=payload.severity,
            status='OPEN',
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
