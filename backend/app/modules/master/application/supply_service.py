from uuid import uuid4

from sqlalchemy import func, insert, select, update

from app.core.database.scope import RecordNotFoundError, VersionConflictError
from app.modules.authentication.infrastructure.authorization import require_permission
from app.modules.master.application.master_deletion import soft_delete_master
from app.modules.master.infrastructure.orm import RawMaterial, Supplier, SupplierMaterial
from app.modules.master.schemas.supply import RawMaterialInput, SupplierInput, SupplierMaterialInput
from app.modules.traceability.infrastructure.registry import sync_source


class SupplyConflictError(Exception):
    pass


class SupplyService:
    def __init__(self, db, scope, kind):
        self.db, self.scope, self.kind = db, scope, kind
        model, self.pk, self.permission, self.input_type, self.asset = {
            'supplier': (Supplier, 'supplier_id', 'Supplier', SupplierInput, 'SUPPLIER'),
            'material': (RawMaterial, 'raw_material_id', 'RawMaterial', RawMaterialInput, 'RAW_MATERIAL'),
            'link': (SupplierMaterial, 'supplier_material_id', 'SupplierMaterial', SupplierMaterialInput, None),
        }[kind]
        self.table = model.__table__

    def _visible(self):
        return self.table.c.tenant_id == self.scope.tenant_id, self.table.c.deleted_at.is_(None)

    def _read_query(self):
        if self.kind != 'link':
            return select(self.table).where(*self._visible())
        return select(
            self.table,
            Supplier.supplier_code,
            Supplier.supplier_name,
            RawMaterial.material_code,
            RawMaterial.material_name,
        ).join(Supplier, (Supplier.tenant_id == self.table.c.tenant_id) &
               (Supplier.supplier_id == self.table.c.supplier_id)).join(
                   RawMaterial, (RawMaterial.tenant_id == self.table.c.tenant_id) &
                   (RawMaterial.raw_material_id == self.table.c.raw_material_id),
               ).where(*self._visible(), Supplier.deleted_at.is_(None), RawMaterial.deleted_at.is_(None))

    async def _get(self, identifier, lock=False):
        query = self._read_query().where(self.table.c[self.pk] == identifier)
        if lock:
            query = query.with_for_update()
        row = (await self.db.execute(query)).mappings().one_or_none()
        if row is None:
            raise RecordNotFoundError('Supply record not found')
        return dict(row)

    async def get(self, identifier):
        await require_permission(self.db, self.scope, f'{self.permission}.Read')
        return await self._get(identifier)

    async def list(self, *, offset=0, limit=20, supplier_id=None, raw_material_id=None):
        if type(offset) is not int or type(limit) is not int or offset < 0 or not 1 <= limit <= 100:
            raise ValueError('Invalid pagination')
        await require_permission(self.db, self.scope, f'{self.permission}.Read')
        query = self._read_query()
        for field, value in (('supplier_id', supplier_id), ('raw_material_id', raw_material_id)):
            if value is not None:
                query = query.where(self.table.c[field] == value)
        rows = (await self.db.execute(query.order_by(self.table.c.created_at.desc(), self.table.c[self.pk].desc())
                                     .offset(offset).limit(limit + 1))).mappings().all()
        return {'items': [dict(r) for r in rows[:limit]], 'offset': offset, 'limit': limit,
                'next_offset': offset + limit if len(rows) > limit else None}

    async def save(self, values, *, identifier=None, expected_version=None):
        await require_permission(self.db, self.scope, f'{self.permission}.Write')
        values = self.input_type.model_validate(values).model_dump()
        if identifier is not None and (type(expected_version) is not int or expected_version < 1):
            raise ValueError('Positive expected_version required')
        if self.kind == 'link':
            # Consistent parent lock order; parent deactivation waits for the link transaction.
            for model, key in ((Supplier, 'supplier_id'), (RawMaterial, 'raw_material_id')):
                parent = await self.db.scalar(select(model.__table__.c[key]).where(
                    model.__table__.c[key] == values[key], model.tenant_id == self.scope.tenant_id,
                    model.deleted_at.is_(None), model.status == 'ACTIVE').with_for_update(read=True))
                if parent is None:
                    raise SupplyConflictError('Active supplier and material in this tenant required')
        if identifier is not None:
            current = await self._get(identifier, lock=True)
            if current['version'] != expected_version:
                raise VersionConflictError('Supply record changed; reload before retrying')
            if self.kind == 'material' and current['uom'] != values['uom']:
                raise SupplyConflictError('Material unit cannot be changed')
        if identifier is None:
            identifier = uuid4()
            await self.db.execute(insert(self.table).values(**values, **{self.pk: identifier}, tenant_id=self.scope.tenant_id,
                created_by=self.scope.actor_id, updated_by=self.scope.actor_id, version=1))
        else:
            await self.db.execute(update(self.table).where(*self._visible(), self.table.c[self.pk] == identifier,
                self.table.c.version == expected_version).values(**values, updated_by=self.scope.actor_id,
                updated_at=func.clock_timestamp(), version=self.table.c.version + 1))
        if self.asset:
            await sync_source(self.db, self.scope, self.asset, identifier)
        return await self._get(identifier)


    async def delete(self, identifier, *, expected_version):
        await require_permission(self.db, self.scope, f'{self.permission}.Delete')
        if type(expected_version) is not int or expected_version < 1:
            raise ValueError('Positive expected_version required')
        current = await self._get(identifier, lock=True)
        if current['version'] != expected_version:
            raise VersionConflictError('Record changed; reload before retrying')
        return await soft_delete_master(self.db, self.scope, self.table, self.pk, current)
