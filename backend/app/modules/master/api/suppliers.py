from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.responses.envelope import Envelope, envelope
from app.modules.master.api.supply_dependencies import supply_dependency
from app.modules.master.application.supply_service import SupplyService
from app.modules.master.schemas.supply import (
    SupplierEnvelope,
    SupplierInput,
    SupplierPageEnvelope,
    SupplierUpdate,
)

router = APIRouter(prefix='/suppliers', tags=['Supplier'], responses={
    400: {'model': Envelope, 'description': 'Invalid input or pagination'},
    401: {'model': Envelope, 'description': 'Invalid bearer session'},
    403: {'model': Envelope, 'description': 'Required Supplier permission missing'},
    404: {'model': Envelope, 'description': 'Supply not found in tenant'},
    409: {'model': Envelope, 'description': 'Duplicate code, stale version or invalid parent'},
    503: {'model': Envelope, 'description': 'Authentication/database unavailable'},
    500: {'model': Envelope, 'description': 'Unexpected server error'},
})
ServiceDep = Annotated[SupplyService, Depends(supply_dependency('supplier'), scope='function')]


@router.get('', response_model=SupplierPageEnvelope, description='Bearer + Supplier.Read. No body; nondeleted tenant records, created_at/ID descending, offset/limit and next_offset.')
async def list_supplies(request: Request, service: ServiceDep,
                         offset: Annotated[int, Query(ge=0, le=2147483647)] = 0,
                         limit: Annotated[int, Query(ge=1, le=100)] = 20):
    return envelope(request, data=await service.list(offset=offset, limit=limit))


@router.get('/{identifier}', response_model=SupplierEnvelope, description='Bearer + Supplier.Read. No body. Missing/deleted/foreign records return 404.')
async def get_supply(request: Request, identifier: UUID, service: ServiceDep):
    return envelope(request, data=await service.get(identifier))


@router.post('', response_model=SupplierEnvelope, status_code=201, description='Bearer + Supplier.Write. Create definition with server tenant/actor. Linked supplier/material must be active in tenant. Supplier/material registry commits atomically.')
async def create_supply(request: Request, payload: SupplierInput, service: ServiceDep):
    return envelope(request, code=201, data=await service.save(payload.model_dump()))


@router.put('/{identifier}', response_model=SupplierEnvelope, description='Bearer + Supplier.Write. Replace definition plus expected_version; omitted optional fields reset to defaults. Status does not cascade to existing supplier-material links. No cascade.')
async def update_supply(request: Request, identifier: UUID, payload: SupplierUpdate, service: ServiceDep):
    return envelope(request, data=await service.save(payload.model_dump(exclude={'expected_version'}), identifier=identifier, expected_version=payload.expected_version))


@router.delete('/{identifier}', response_model=SupplierEnvelope,
               description='Bearer + Supplier.Delete, independent of Read/Write. No body; expected_version query required. Soft delete only, no cascade. Nondeleted references block with 409, including INACTIVE children. Returns deleted snapshot; subsequent access/retry 404. Registry deletion is atomic where applicable.')
async def delete_record(request: Request, identifier: UUID, service: ServiceDep,
                        expected_version: Annotated[int, Query(ge=1, le=2147483647)]):
    if await request.body():
        raise HTTPException(400, 'Request body must be empty')
    return envelope(request, data=await service.delete(identifier, expected_version=expected_version))
