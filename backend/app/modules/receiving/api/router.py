from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.exc import IntegrityError

from app.core.database.scope import ActorScope, RecordNotFoundError, VersionConflictError
from app.core.responses.envelope import Envelope, envelope
from app.modules.authentication.api.router import DatabaseDep, current_account
from app.modules.authentication.application.account_service import AuthenticatedAccount
from app.modules.authentication.infrastructure.authorization import PermissionDeniedError
from app.modules.receiving.application.service import ReceivingConflictError, ReceivingService
from app.modules.receiving.schemas.receiving import (
    BatchEnvelope,
    BatchPageEnvelope,
    CancelInput,
    CompleteInput,
    ReceivingEnvelope,
    ReceivingInput,
    ReceivingPageEnvelope,
)

router = APIRouter(tags=['Receiving'], responses={
    400: {'model': Envelope, 'description': 'Invalid payload, path or query'},
    401: {'model': Envelope, 'description': 'Invalid bearer session'},
    403: {'model': Envelope, 'description': 'Required permission is not granted'},
    404: {'model': Envelope, 'description': 'Receiving or batch not found in tenant'},
    409: {'model': Envelope, 'description': 'Stale version, duplicate batch/QR, invalid parent or transition'},
    500: {'model': Envelope, 'description': 'Unexpected server error'},
    503: {'model': Envelope, 'description': 'Authentication/database unavailable'},
})


async def service_dependency(db: DatabaseDep,
    account: Annotated[AuthenticatedAccount, Depends(current_account, scope='function')]):
    try:
        yield ReceivingService(db, ActorScope(account.tenant_id, account.user_id))
    except PermissionDeniedError:
        raise HTTPException(403, 'Required permission is not granted') from None
    except RecordNotFoundError:
        raise HTTPException(404, 'Receiving or batch not found') from None
    except VersionConflictError:
        raise HTTPException(409, 'Receiving changed; reload before retrying') from None
    except ReceivingConflictError as exc:
        raise HTTPException(409, str(exc)) from None
    except IntegrityError as exc:
        if getattr(exc.orig, 'sqlstate', None) == '23505':
            raise HTTPException(409, 'Batch code or QR already exists in this tenant') from None
        if getattr(exc.orig, 'sqlstate', None) == '23503':
            raise HTTPException(409, 'Receiving reference unavailable') from None
        raise


ServiceDep = Annotated[ReceivingService, Depends(service_dependency, scope='function')]
Offset = Annotated[int, Query(ge=0, le=2147483647)]
Limit = Annotated[int, Query(ge=1, le=100)]


@router.post('/receivings', status_code=201, response_model=ReceivingEnvelope,
    description='Receiving.Write. Atomic header + 1..100 items/batches, registry and stored receiving.created event. Active tenant parents and supplier-material link required. UOM/tenant/operator are server-derived. No stock ledger yet.')
async def create_receiving(request: Request, payload: ReceivingInput, service: ServiceDep):
    return envelope(request, code=201, data=await service.create(payload))


@router.get('/receivings', response_model=ReceivingPageEnvelope,
    description='Receiving.Read. No body. Nondeleted tenant headers (no nested items), created_at/ID descending; optional AND filters, offset/limit and nullable next_offset.')
async def list_receivings(request: Request, service: ServiceDep, offset: Offset = 0, limit: Limit = 20,
    supplier_id: UUID | None = None, kitchen_id: UUID | None = None,
    status: Literal['CREATED', 'COMPLETED', 'CANCELLED'] | None = None):
    return envelope(request, data=await service.list(offset=offset, limit=limit,
        supplier_id=supplier_id, kitchen_id=kitchen_id, status=status))


@router.get('/receivings/{identifier}', response_model=ReceivingEnvelope,
    description='Receiving.Read. UUID path; no body/query. Tenant header with all items and nested batches, items sorted by UUID ascending; missing/foreign/deleted returns 404.')
async def get_receiving(request: Request, identifier: UUID, service: ServiceDep):
    return envelope(request, data=await service.get(identifier))


@router.post('/receivings/{identifier}/complete', response_model=ReceivingEnvelope,
    description='Receiving.Complete. CREATED only, expected_version and exactly one boolean decision per item required. Expired before current UTC date cannot be accepted. COMPLETED plus ACCEPTED/REJECTED batches; accepted batches add SUPPLIED/RECEIVED edges and RECEIVING movement to kitchen. Atomic registry and stored event. Retry after success returns 409; reload first.')
async def complete_receiving(request: Request, identifier: UUID, payload: CompleteInput, service: ServiceDep):
    return envelope(request, data=await service.finalize(identifier, payload))


@router.post('/receivings/{identifier}/cancel', response_model=ReceivingEnvelope,
    description='Receiving.Cancel. CREATED only, expected_version required. Header/batches become CANCELLED; item.accepted stays null. Atomic registry and stored event; no movement. No deletion or reversal of completed receipts. Retry after success returns 409.')
async def cancel_receiving(request: Request, identifier: UUID, payload: CancelInput, service: ServiceDep):
    return envelope(request, data=await service.finalize(identifier, payload, cancel=True))


@router.get('/raw-material-batches', response_model=BatchPageEnvelope,
    description='RawMaterialBatch.Read. No body; nondeleted tenant batches, created_at/ID descending; optional AND filters, offset/limit and next_offset. Status is a receiving decision, not an available-stock balance.')
async def list_batches(request: Request, service: ServiceDep, offset: Offset = 0, limit: Limit = 20,
    receiving_id: UUID | None = None, raw_material_id: UUID | None = None, supplier_id: UUID | None = None,
    status: Literal['CREATED', 'ACCEPTED', 'REJECTED', 'CANCELLED'] | None = None):
    return envelope(request, data=await service.list(batch=True, offset=offset, limit=limit,
        receiving_id=receiving_id, raw_material_id=raw_material_id, supplier_id=supplier_id, status=status))


@router.get('/raw-material-batches/{identifier}', response_model=BatchEnvelope,
    description='RawMaterialBatch.Read. UUID path; no body/query. Missing/foreign/deleted returns 404. Batches are created/finalized only through receiving; no direct edit/delete endpoint.')
async def get_batch(request: Request, identifier: UUID, service: ServiceDep):
    return envelope(request, data=await service.get(identifier, batch=True))
