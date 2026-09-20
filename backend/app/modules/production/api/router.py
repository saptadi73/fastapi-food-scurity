from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.exc import IntegrityError

from app.core.database.scope import ActorScope, RecordNotFoundError, VersionConflictError
from app.core.responses.envelope import Envelope, envelope
from app.modules.authentication.api.router import DatabaseDep, current_account
from app.modules.authentication.application.account_service import AuthenticatedAccount
from app.modules.authentication.infrastructure.authorization import PermissionDeniedError
from app.modules.production.application.service import ProductionConflictError, ProductionService
from app.modules.production.schemas.production import (
    CancelInput,
    FinishInput,
    ProductionEnvelope,
    ProductionInput,
    ProductionPageEnvelope,
    StartInput,
)

router = APIRouter(prefix='/production-batches', tags=['Production'], responses={
    400: {'model': Envelope, 'description': 'Invalid payload, path or query'},
    401: {'model': Envelope, 'description': 'Invalid bearer session'},
    403: {'model': Envelope, 'description': 'Required permission is not granted'},
    404: {'model': Envelope, 'description': 'Production batch not found in tenant'},
    409: {'model': Envelope, 'description': 'Stale version, duplicate batch/QR, invalid parent or transition'},
    500: {'model': Envelope, 'description': 'Unexpected server error'},
    503: {'model': Envelope, 'description': 'Authentication/database unavailable'},
})


async def service_dependency(db: DatabaseDep,
    account: Annotated[AuthenticatedAccount, Depends(current_account, scope='function')]):
    try:
        yield ProductionService(db, ActorScope(account.tenant_id, account.user_id))
    except PermissionDeniedError:
        raise HTTPException(403, 'Required permission is not granted') from None
    except RecordNotFoundError:
        raise HTTPException(404, 'Production batch not found') from None
    except VersionConflictError:
        raise HTTPException(409, 'Production or material batch changed; reload before retrying') from None
    except ProductionConflictError as exc:
        raise HTTPException(409, str(exc)) from None
    except IntegrityError as exc:
        if getattr(exc.orig, 'sqlstate', None) == '23505':
            raise HTTPException(409, 'Production batch code already exists in this tenant') from None
        if getattr(exc.orig, 'sqlstate', None) == '23503':
            raise HTTPException(409, 'Production reference unavailable') from None
        raise


ServiceDep = Annotated[ProductionService, Depends(service_dependency, scope='function')]
Offset = Annotated[int, Query(ge=0, le=2147483647)]
Limit = Annotated[int, Query(ge=1, le=100)]


@router.post('', status_code=201, response_model=ProductionEnvelope,
    description='Production.Write. Create planned batch and frozen recipe snapshot; active kitchen/menu/material required, 1..100 recipe lines. Requirements rounded half-up to 6 decimals. No stock reserved. Atomic registry/event.')
async def create(request: Request, payload: ProductionInput, service: ServiceDep):
    return envelope(request, code=201, data=await service.create(payload))


@router.get('', response_model=ProductionPageEnvelope,
    description='Production.Read. No body; tenant nondeleted headers with recipe snapshot, optional kitchen/menu/status AND filters. created_at/ID descending; offset/limit and nullable next_offset.')
async def listing(request: Request, service: ServiceDep, offset: Offset = 0, limit: Limit = 20,
    kitchen: UUID | None = None, menu: UUID | None = None,
    status: Literal['CREATED', 'RUNNING', 'COMPLETED', 'CANCELLED'] | None = None):
    return envelope(request, data=await service.list(offset=offset, limit=limit, kitchen=kitchen, menu=menu, status=status))


@router.get('/{identifier}', response_model=ProductionEnvelope,
    description='Production.Read. UUID path; no body/query. Header, snapshot and consumed items sorted by item UUID. Foreign/deleted/missing returns 404.')
async def detail(request: Request, identifier: UUID, service: ServiceDep):
    return envelope(request, data=await service.get(identifier))


@router.post('/{identifier}/start', response_model=ProductionEnvelope,
    description='Production.Start. CREATED only; production expected_version plus 1..100 unique material batches with expected_version/storage_id/quantity. Exact snapshot requirements, available unexpired stock and active same-kitchen parents required. One storage per material batch per production. Atomic stock issues, batch versions, USED graph, ISSUE movements, registry and event. Retry stale 409.')
async def start(request: Request, identifier: UUID, payload: StartInput, service: ServiceDep):
    return envelope(request, data=await service.start(identifier, payload))


@router.post('/{identifier}/complete', response_model=ProductionEnvelope,
    description='Production.Complete. RUNNING only; expected_version, actual_quantity 0..planned, optional initial_temperature and food_sensor_device_uuid. An active food sensor creates a PRODUCTION binding for subsequent temperature ingestion. No stock refund for yield loss; server UTC completion. Atomic registry/event. Holding and packaging are separate.')
async def complete(request: Request, identifier: UUID, payload: FinishInput, service: ServiceDep):
    return envelope(request, data=await service.finish(identifier, payload))


@router.post('/{identifier}/cancel', response_model=ProductionEnvelope,
    description='Production.Cancel. CREATED only; expected_version. Atomic registry/event, no stock effect. No running cancellation or reversal.')
async def cancel(request: Request, identifier: UUID, payload: CancelInput, service: ServiceDep):
    return envelope(request, data=await service.finish(identifier, payload, cancel=True))
