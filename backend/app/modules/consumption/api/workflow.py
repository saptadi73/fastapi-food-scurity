from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.exc import IntegrityError

from app.core.database.scope import ActorScope, RecordNotFoundError, VersionConflictError
from app.core.responses.envelope import Envelope, envelope
from app.modules.authentication.api.router import DatabaseDep, current_account
from app.modules.authentication.application.account_service import AuthenticatedAccount
from app.modules.authentication.infrastructure.authorization import PermissionDeniedError
from app.modules.consumption.application.service import (
    SchoolWorkflowConflictError,
    SchoolWorkflowService,
)
from app.modules.consumption.schemas.workflow import (
    ConsumptionEnvelope,
    ConsumptionInput,
    ConsumptionPageEnvelope,
    ReceiptEnvelope,
    ReceiptInput,
    ReceiptPageEnvelope,
)

router = APIRouter(tags=['School receiving and consumption'], responses={
    400: {'model': Envelope, 'description': 'Invalid payload, path or query'},
    401: {'model': Envelope, 'description': 'Invalid bearer session'},
    403: {'model': Envelope, 'description': 'Required permission is not granted'},
    404: {'model': Envelope, 'description': 'Record not found in tenant'},
    409: {'model': Envelope, 'description': 'Stale version, duplicate record, invalid parent or transition'},
    500: {'model': Envelope, 'description': 'Unexpected server error'},
    503: {'model': Envelope, 'description': 'Authentication/database unavailable'},
})


async def service_dependency(db: DatabaseDep,
    account: Annotated[AuthenticatedAccount, Depends(current_account, scope='function')]):
    try:
        yield SchoolWorkflowService(db, ActorScope(account.tenant_id, account.user_id))
    except PermissionDeniedError:
        raise HTTPException(403, 'Required permission is not granted') from None
    except RecordNotFoundError:
        raise HTTPException(404, 'Record not found') from None
    except VersionConflictError:
        raise HTTPException(409, 'Package changed; reload before retrying') from None
    except SchoolWorkflowConflictError as exc:
        raise HTTPException(409, str(exc)) from None
    except IntegrityError as exc:
        if getattr(exc.orig, 'sqlstate', None) == '23505':
            raise HTTPException(409, 'Receiving or consumption already recorded') from None
        if getattr(exc.orig, 'sqlstate', None) == '23503':
            raise HTTPException(409, 'Reference unavailable') from None
        raise


ServiceDep = Annotated[SchoolWorkflowService, Depends(service_dependency, scope='function')]
Offset = Annotated[int, Query(ge=0, le=2147483647)]
Limit = Annotated[int, Query(ge=1, le=100)]


@router.post('/school-receivings', status_code=201, response_model=ReceiptEnvelope,
    description='SchoolReceiving.Write. Immutable decision for a delivered manifest package; expected_version is package version. Server timestamp, known quantity, GOOD/unexpired acceptance; rejection and shortage require notes. Atomic package RECEIVED/REJECTED and version, traceability, movement and event.')
async def receive(request: Request, payload: ReceiptInput, service: ServiceDep):
    return envelope(request, code=201, data=await service.receive(payload))


@router.get('/school-receivings', response_model=ReceiptPageEnvelope,
    description='SchoolReceiving.Read. No body; tenant records, optional package_id/school/delivery_id AND filters. created_at/ID descending, offset pagination.')
async def receipts(request: Request, service: ServiceDep, offset: Offset = 0, limit: Limit = 20,
    package_id: UUID | None = None, school: UUID | None = None, delivery_id: UUID | None = None):
    return envelope(request, data=await service.list_records('receipt', offset, limit, package_id, school, delivery_id))


@router.get('/school-receivings/{identifier}', response_model=ReceiptEnvelope,
    description='SchoolReceiving.Read. UUID path, no body/query. Immutable evidence, not live package state. Missing/foreign record 404.')
async def receipt(request: Request, identifier: UUID, service: ServiceDep):
    return envelope(request, data=await service.read_record('receipt', identifier))


@router.post('/consumptions', status_code=201, response_model=ConsumptionEnvelope,
    description='Consumption.Write. Finalize RECEIVED package once; expected_version is package version. Consumed plus discarded equals accepted quantity. Server time; discard or expired/unknown holding consumption requires notes. safe is holding-only snapshot, null when all discarded. Atomic package status/version, traceability, movements and event.')
async def consume(request: Request, payload: ConsumptionInput, service: ServiceDep):
    return envelope(request, code=201, data=await service.consume(payload))


@router.get('/consumptions', response_model=ConsumptionPageEnvelope,
    description='Consumption.Read. No body; optional package_id UUID, tenant filter, created_at/ID descending, offset pagination.')
async def consumptions(request: Request, service: ServiceDep, offset: Offset = 0, limit: Limit = 20,
    package_id: UUID | None = None):
    return envelope(request, data=await service.list_records('consumption', offset, limit, package_id))


@router.get('/consumptions/{identifier}', response_model=ConsumptionEnvelope,
    description='Consumption.Read. UUID path, no body/query. Immutable historical holding and quantity snapshot; missing/foreign 404.')
async def consumption(request: Request, identifier: UUID, service: ServiceDep):
    return envelope(request, data=await service.read_record('consumption', identifier))
