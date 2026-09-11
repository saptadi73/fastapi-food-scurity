from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.responses.envelope import Envelope, envelope
from app.modules.master.api.food_dependencies import food_dependency
from app.modules.master.application.food_service import FoodService
from app.modules.master.schemas.food import (
    RecipeEnvelope,
    RecipeInput,
    RecipePageEnvelope,
    RecipeUpdate,
)

router = APIRouter(prefix='/recipes', tags=['Recipe'], responses={
    400: {'model': Envelope, 'description': 'Invalid input or pagination'},
    401: {'model': Envelope, 'description': 'Invalid bearer session'},
    403: {'model': Envelope, 'description': 'Required Recipe permission missing'},
    404: {'model': Envelope, 'description': 'Food not found in tenant'},
    409: {'model': Envelope, 'description': 'Duplicate code, stale version or invalid parent'},
    503: {'model': Envelope, 'description': 'Authentication/database unavailable'},
    500: {'model': Envelope, 'description': 'Unexpected server error'},
})
ServiceDep = Annotated[FoodService, Depends(food_dependency('recipe'), scope='function')]


@router.get('', response_model=RecipePageEnvelope, description='Bearer + Recipe.Read. No body; nondeleted tenant records; optional food_item_id/raw_material_id UUID AND filters, created_at/ID descending, offset/limit and next_offset.')
async def list_records(request: Request, service: ServiceDep,
                         offset: Annotated[int, Query(ge=0, le=2147483647)] = 0,
                         limit: Annotated[int, Query(ge=1, le=100)] = 20,
                         food_item_id: Annotated[UUID | None, Query()] = None,
                         raw_material_id: Annotated[UUID | None, Query()] = None):
    return envelope(request, data=await service.list(offset=offset, limit=limit, food_item_id=food_item_id, raw_material_id=raw_material_id))


@router.get('/{identifier}', response_model=RecipeEnvelope, description='Bearer + Recipe.Read. No body. Missing/deleted/foreign records return 404.')
async def get_record(request: Request, identifier: UUID, service: ServiceDep):
    return envelope(request, data=await service.get(identifier))


@router.post('', response_model=RecipeEnvelope, status_code=201, description='Bearer + Recipe.Write. Create definition with server tenant/actor. Recipe requires active food/material in tenant and uom matching material; quantity is per one food output unit. No stock or production is created.')
async def create_record(request: Request, payload: RecipeInput, service: ServiceDep):
    return envelope(request, code=201, data=await service.save(payload.model_dump()))


@router.put('/{identifier}', response_model=RecipeEnvelope, description='Bearer + Recipe.Write. Replace definition plus expected_version; omitted optional fields reset to defaults. Food/material pair is immutable; active parents and matching material uom required. Quantity is per one food output unit. No cascade.')
async def update_record(request: Request, identifier: UUID, payload: RecipeUpdate, service: ServiceDep):
    return envelope(request, data=await service.save(payload.model_dump(exclude={'expected_version'}), identifier=identifier, expected_version=payload.expected_version))


@router.delete('/{identifier}', response_model=RecipeEnvelope,
               description='Bearer + Recipe.Delete, independent of Read/Write. No body; expected_version query required. Soft delete only, no cascade. Nondeleted references block with 409, including INACTIVE children. Returns deleted snapshot; subsequent access/retry 404. Food deletion is blocked by nondeleted recipes or production batches; recipe deletion keeps its pair reserved.')
async def delete_record(request: Request, identifier: UUID, service: ServiceDep,
                        expected_version: Annotated[int, Query(ge=1, le=2147483647)]):
    if await request.body():
        raise HTTPException(400, 'Request body must be empty')
    return envelope(request, data=await service.delete(identifier, expected_version=expected_version))
