from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.responses.envelope import Envelope, envelope
from app.modules.master.api.packaging_dependencies import packaging_dependency
from app.modules.master.application.packaging_service import PackagingTypeService
from app.modules.master.schemas.packaging import (
    PackagingTypeEnvelope,
    PackagingTypeInput,
    PackagingTypePageEnvelope,
    PackagingTypeUpdate,
)

router = APIRouter(prefix='/packaging-types', tags=['PackagingType'], responses={
    400: {'model': Envelope, 'description': 'Invalid input or pagination'},
    401: {'model': Envelope, 'description': 'Invalid bearer session'},
    403: {'model': Envelope, 'description': 'Required PackagingType permission missing'},
    404: {'model': Envelope, 'description': 'Packaging type not found in tenant'},
    409: {'model': Envelope, 'description': 'Duplicate code, stale version or invalid parent'},
    503: {'model': Envelope, 'description': 'Authentication/database unavailable'},
    500: {'model': Envelope, 'description': 'Unexpected server error'},
})
ServiceDep = Annotated[PackagingTypeService, Depends(packaging_dependency('packaging'), scope='function')]


@router.get('', response_model=PackagingTypePageEnvelope, description='Bearer + PackagingType.Read. No body; nondeleted tenant records, created_at/ID descending, offset/limit and next_offset.')
async def list_records(request: Request, service: ServiceDep,
                         offset: Annotated[int, Query(ge=0, le=2147483647)] = 0,
                         limit: Annotated[int, Query(ge=1, le=100)] = 20):
    return envelope(request, data=await service.list(offset=offset, limit=limit))


@router.get('/{identifier}', response_model=PackagingTypeEnvelope, description='Bearer + PackagingType.Read. No body. Missing/deleted/foreign records return 404.')
async def get_record(request: Request, identifier: UUID, service: ServiceDep):
    return envelope(request, data=await service.get(identifier))


@router.post('', response_model=PackagingTypeEnvelope, status_code=201, description='Bearer + PackagingType.Write. Create definition with server tenant/actor. Code unique per tenant including soft-deleted rows; volume is in milliliters, optional positive decimal. No status field. No stock or production is created.')
async def create_record(request: Request, payload: PackagingTypeInput, service: ServiceDep):
    return envelope(request, code=201, data=await service.save(payload.model_dump()))


@router.put('/{identifier}', response_model=PackagingTypeEnvelope, description='Bearer + PackagingType.Write. Replace definition plus expected_version; omitted optional fields reset to defaults. Volume in milliliters. No cascade.')
async def update_record(request: Request, identifier: UUID, payload: PackagingTypeUpdate, service: ServiceDep):
    return envelope(request, data=await service.save(payload.model_dump(exclude={'expected_version'}), identifier=identifier, expected_version=payload.expected_version))


@router.delete('/{identifier}', response_model=PackagingTypeEnvelope,
               description='Bearer + PackagingType.Delete, independent of Read/Write. No body; expected_version query required. Soft delete only, no cascade. Nondeleted references block with 409, including INACTIVE children. Returns deleted snapshot; subsequent access/retry 404. Nondeleted packages block deletion; code remains reserved.')
async def delete_record(request: Request, identifier: UUID, service: ServiceDep,
                        expected_version: Annotated[int, Query(ge=1, le=2147483647)]):
    if await request.body():
        raise HTTPException(400, 'Request body must be empty')
    return envelope(request, data=await service.delete(identifier, expected_version=expected_version))
