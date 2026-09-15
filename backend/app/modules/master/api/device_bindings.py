from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.responses.envelope import Envelope, envelope
from app.modules.master.api.device_binding_dependencies import device_binding_dependency
from app.modules.master.application.device_binding_service import DeviceBindingService
from app.modules.master.schemas.fleet import (
    DeviceBindingEnvelope,
    DeviceBindingInput,
    DeviceBindingPageEnvelope,
    DeviceBindingUpdate,
)

router = APIRouter(prefix='/device-bindings', tags=['DeviceBinding'], responses={
    400: {'model': Envelope, 'description': 'Invalid input or pagination'},
    401: {'model': Envelope, 'description': 'Invalid bearer session'},
    403: {'model': Envelope, 'description': 'Required Device permission is not granted'},
    404: {'model': Envelope, 'description': 'Device binding not found'},
    409: {'model': Envelope, 'description': 'Duplicate binding, stale version or invalid parent'},
    503: {'model': Envelope, 'description': 'Authentication/database unavailable'},
    500: {'model': Envelope, 'description': 'Unexpected server error'},
})
ServiceDep = Annotated[DeviceBindingService, Depends(device_binding_dependency(), scope='function')]


@router.get('', response_model=DeviceBindingPageEnvelope, description='Bearer + Device.Read. No body; nondeleted tenant records, created_at/ID descending, offset/limit and next_offset.')
async def list_bindings(request: Request, service: ServiceDep,
                        offset: Annotated[int, Query(ge=0, le=2147483647)] = 0,
                        limit: Annotated[int, Query(ge=1, le=100)] = 20,
                        device_id: Annotated[UUID | None, Query()] = None,
                        vehicle_id: Annotated[UUID | None, Query()] = None):
    return envelope(request, data=await service.list(offset=offset, limit=limit, device_id=device_id, vehicle_id=vehicle_id))


@router.get('/{identifier}', response_model=DeviceBindingEnvelope, description='Bearer + Device.Read. No body. Missing/deleted/foreign records return 404.')
async def get_binding(request: Request, identifier: UUID, service: ServiceDep):
    return envelope(request, data=await service.get(identifier))


@router.post('', response_model=DeviceBindingEnvelope, status_code=201, description='Bearer + Device.Write. Create binding with server tenant/actor. Device must be active GPS, vehicle must be active, both same tenant.')
async def create_binding(request: Request, payload: DeviceBindingInput, service: ServiceDep):
    return envelope(request, code=201, data=await service.save(payload.model_dump()))


@router.put('/{identifier}', response_model=DeviceBindingEnvelope, description='Bearer + Device.Write. Replace binding plus expected_version; omitted optional fields reset to defaults.')
async def update_binding(request: Request, identifier: UUID, payload: DeviceBindingUpdate, service: ServiceDep):
    return envelope(request, data=await service.save(payload.model_dump(exclude={'expected_version'}), identifier=identifier, expected_version=payload.expected_version))


@router.delete('/{identifier}', response_model=DeviceBindingEnvelope,
               description='Bearer + Device.Delete, independent of Read/Write. No body; expected_version query required. Soft delete only, no cascade. Nondeleted references block with 409, including INACTIVE children. Returns deleted snapshot; subsequent access/retry 404.')
async def delete_binding(request: Request, identifier: UUID, service: ServiceDep,
                        expected_version: Annotated[int, Query(ge=1, le=2147483647)]):
    if await request.body():
        raise HTTPException(400, 'Request body must be empty')
    return envelope(request, data=await service.delete(identifier, expected_version=expected_version))
