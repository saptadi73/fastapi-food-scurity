from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.responses.envelope import Envelope, envelope
from app.modules.master.api.location_dependencies import location_dependency
from app.modules.master.application.location_service import LocationService
from app.modules.master.schemas.fleet import (
    DriverEnvelope,
    DriverInput,
    DriverPageEnvelope,
    DriverUpdate,
)

router = APIRouter(prefix='/drivers', tags=['Driver'], responses={
    400: {'model': Envelope, 'description': 'Invalid input or pagination'},
    401: {'model': Envelope, 'description': 'Invalid bearer session'},
    403: {'model': Envelope, 'description': 'Required Driver permission missing'},
    404: {'model': Envelope, 'description': 'Location not found in tenant'},
    409: {'model': Envelope, 'description': 'Duplicate code, stale version or invalid parent'},
    503: {'model': Envelope, 'description': 'Authentication/database unavailable'},
    500: {'model': Envelope, 'description': 'Unexpected server error'},
})
ServiceDep = Annotated[LocationService, Depends(location_dependency('driver'), scope='function')]


@router.get('', response_model=DriverPageEnvelope, description='Bearer + Driver.Read. No body; nondeleted tenant records, created_at/ID descending, offset/limit and next_offset.')
async def list_locations(request: Request, service: ServiceDep,
                         offset: Annotated[int, Query(ge=0, le=2147483647)] = 0,
                         limit: Annotated[int, Query(ge=1, le=100)] = 20):
    return envelope(request, data=await service.list(offset=offset, limit=limit))


@router.get('/{identifier}', response_model=DriverEnvelope, description='Bearer + Driver.Read. No body. Missing/deleted/foreign records return 404.')
async def get_location(request: Request, identifier: UUID, service: ServiceDep):
    return envelope(request, data=await service.get(identifier))


@router.post('', response_model=DriverEnvelope, status_code=201, description='Bearer + Driver.Write. Create definition with server tenant/actor. Driver definition with server tenant/actor; driver has no registry.')
async def create_location(request: Request, payload: DriverInput, service: ServiceDep):
    return envelope(request, code=201, data=await service.save(payload.model_dump()))


@router.put('/{identifier}', response_model=DriverEnvelope, description='Bearer + Driver.Write. Replace definition plus expected_version; omitted optional fields reset to defaults. Driver status changes do not cascade to vehicles or deliveries. No cascade.')
async def update_location(request: Request, identifier: UUID, payload: DriverUpdate, service: ServiceDep):
    return envelope(request, data=await service.save(payload.model_dump(exclude={'expected_version'}), identifier=identifier, expected_version=payload.expected_version))


@router.delete('/{identifier}', response_model=DriverEnvelope,
               description='Bearer + Driver.Delete, independent of Read/Write. No body; expected_version query required. Soft delete only, no cascade. Nondeleted references block with 409, including INACTIVE children. Returns deleted snapshot; subsequent access/retry 404. Registry deletion is atomic where applicable.')
async def delete_record(request: Request, identifier: UUID, service: ServiceDep,
                        expected_version: Annotated[int, Query(ge=1, le=2147483647)]):
    if await request.body():
        raise HTTPException(400, 'Request body must be empty')
    return envelope(request, data=await service.delete(identifier, expected_version=expected_version))
