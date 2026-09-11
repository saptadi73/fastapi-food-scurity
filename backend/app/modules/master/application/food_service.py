from uuid import uuid4

from sqlalchemy import func, insert, select, update

from app.core.database.scope import RecordNotFoundError, VersionConflictError
from app.modules.authentication.infrastructure.authorization import require_permission
from app.modules.master.application.master_deletion import soft_delete_master
from app.modules.master.infrastructure.orm import FoodItem, RawMaterial, Recipe
from app.modules.master.schemas.food import FoodItemInput, RecipeInput


class FoodConflictError(Exception):
    pass


class FoodService:
    def __init__(self, db, scope, kind):
        self.db, self.scope, self.kind = db, scope, kind
        model, self.pk, self.permission, self.input_type = {
            'food': (FoodItem, 'food_item_id', 'FoodItem', FoodItemInput),
            'recipe': (Recipe, 'recipe_id', 'Recipe', RecipeInput),
        }[kind]
        self.table = model.__table__

    def _visible(self):
        return self.table.c.tenant_id == self.scope.tenant_id, self.table.c.deleted_at.is_(None)

    async def _get(self, identifier, lock=False):
        query = select(self.table).where(*self._visible(), self.table.c[self.pk] == identifier)
        if lock:
            query = query.with_for_update()
        row = (await self.db.execute(query)).mappings().one_or_none()
        if row is None:
            raise RecordNotFoundError('Food record not found')
        return dict(row)

    async def get(self, identifier):
        await require_permission(self.db, self.scope, f'{self.permission}.Read')
        return await self._get(identifier)

    async def list(self, *, offset=0, limit=20, food_item_id=None, raw_material_id=None, status=None):
        if type(offset) is not int or type(limit) is not int or offset < 0 or not 1 <= limit <= 100:
            raise ValueError('Invalid pagination')
        await require_permission(self.db, self.scope, f'{self.permission}.Read')
        query = select(self.table).where(*self._visible())
        for field, value in (('food_item_id', food_item_id), ('raw_material_id', raw_material_id), ('status', status)):
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
        if self.kind == 'recipe':
            # Food before material before recipe, shared with parent deletion locks.
            parents = {}
            for model, key in ((FoodItem, 'food_item_id'), (RawMaterial, 'raw_material_id')):
                parent = (await self.db.execute(select(model.__table__).where(
                    model.__table__.c[key] == values[key], model.tenant_id == self.scope.tenant_id,
                    model.deleted_at.is_(None), model.status == 'ACTIVE').with_for_update(read=True))).mappings().one_or_none()
                if parent is None:
                    raise FoodConflictError('Active food item and material in this tenant required')
                parents[key] = parent
            if values['uom'] != parents['raw_material_id']['uom']:
                raise FoodConflictError('Recipe unit must match material unit')
        if identifier is not None:
            current = await self._get(identifier, lock=True)
            if current['version'] != expected_version:
                raise VersionConflictError('Food record changed; reload before retrying')
            if self.kind == 'food' and current['uom'] != values['uom']:
                raise FoodConflictError('Food item unit cannot be changed')
            if self.kind == 'recipe' and any(current[key] != values[key] for key in ('food_item_id', 'raw_material_id')):
                raise FoodConflictError('Recipe food item and material cannot be changed')
        if identifier is None:
            identifier = uuid4()
            await self.db.execute(insert(self.table).values(**values, **{self.pk: identifier}, tenant_id=self.scope.tenant_id,
                created_by=self.scope.actor_id, updated_by=self.scope.actor_id, version=1))
        else:
            for key in (('uom',) if self.kind == 'food' else ('food_item_id', 'raw_material_id')):
                values.pop(key)
            await self.db.execute(update(self.table).where(*self._visible(), self.table.c[self.pk] == identifier,
                self.table.c.version == expected_version).values(**values, updated_by=self.scope.actor_id,
                updated_at=func.clock_timestamp(), version=self.table.c.version + 1))
        return await self._get(identifier)


    async def delete(self, identifier, *, expected_version):
        await require_permission(self.db, self.scope, f'{self.permission}.Delete')
        if type(expected_version) is not int or expected_version < 1:
            raise ValueError('Positive expected_version required')
        current = await self._get(identifier, lock=True)
        if current['version'] != expected_version:
            raise VersionConflictError('Record changed; reload before retrying')
        return await soft_delete_master(self.db, self.scope, self.table, self.pk, current)
