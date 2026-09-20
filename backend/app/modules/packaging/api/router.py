from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.exc import IntegrityError

from app.core.database.scope import ActorScope, RecordNotFoundError, VersionConflictError
from app.core.responses.envelope import Envelope, envelope
from app.modules.authentication.api.router import DatabaseDep, current_account
from app.modules.authentication.application.account_service import AuthenticatedAccount
from app.modules.authentication.infrastructure.authorization import PermissionDeniedError
from app.modules.packaging.application.service import PackageService, PackagingConflictError
from app.modules.packaging.schemas.packages import (
    AllocationEnvelope,
    HoldingFinishInput,
    HoldingInput,
    PackageDeliveryContextEnvelope,
    PackageEnvelope,
    PackageInput,
    PackagePageEnvelope,
)

router = APIRouter(tags=['Packaging'], responses={
    400: {'model': Envelope, 'description': 'Invalid payload, path or query'},
    401: {'model': Envelope, 'description': 'Invalid bearer session'},
    403: {'model': Envelope, 'description': 'Required permission is not granted'},
    404: {'model': Envelope, 'description': 'Package or production not found in tenant'},
    409: {'model': Envelope, 'description': 'Stale version, duplicate batch/QR, invalid parent or transition'},
    500: {'model': Envelope, 'description': 'Unexpected server error'},
    503: {'model': Envelope, 'description': 'Authentication/database unavailable'},
})


async def service_dependency(db: DatabaseDep,
    account: Annotated[AuthenticatedAccount, Depends(current_account, scope='function')]):
    try:
        yield PackageService(db, ActorScope(account.tenant_id, account.user_id))
    except PermissionDeniedError:
        raise HTTPException(403, 'Required permission is not granted') from None
    except RecordNotFoundError:
        raise HTTPException(404, 'Package or production not found') from None
    except VersionConflictError:
        raise HTTPException(409, 'Package or production changed; reload before retrying') from None
    except PackagingConflictError as exc:
        raise HTTPException(409, str(exc)) from None
    except IntegrityError as exc:
        if getattr(exc.orig, 'sqlstate', None) == '23505':
            raise HTTPException(409, 'Package code or number already exists in this tenant') from None
        if getattr(exc.orig, 'sqlstate', None) == '23503':
            raise HTTPException(409, 'Packaging reference unavailable') from None
        raise


ServiceDep = Annotated[PackageService, Depends(service_dependency, scope='function')]
Offset = Annotated[int, Query(ge=0, le=2147483647)]
Limit = Annotated[int, Query(ge=1, le=100)]


@router.post('/packages', status_code=201, response_model=PackageEnvelope,
    description='Package.Write. Allocate positive quantity from completed production with expected_version of production and optional initial_temperature. Kitchen and packaging type same tenant; no over-allocation, including discarded packages. Freeze holding policy once; expiry anchored to cooking finish. Atomic production version, package registry, PACKAGED edge, movement and event. QR payload identifies UUID; rendering is client-side.')
async def create(request: Request, payload: PackageInput, service: ServiceDep):
    return envelope(request, code=201, data=await service.create(payload))


@router.get('/packages', response_model=PackagePageEnvelope,
    description='Package.Read. No body; optional production_batch_id, offset/limit. Tenant nondeleted, created_at/ID descending. Timer is evaluated at response time without writes; status persisted, effective_status reflects expiry.')
async def listing(request: Request, service: ServiceDep, offset: Offset = 0, limit: Limit = 20, production_batch_id: UUID | None = None):
    return envelope(request, data=await service.list(offset=offset, limit=limit, production_batch_id=production_batch_id))


@router.get('/packages/resolve', response_model=PackageEnvelope,
    description='Package.Read. No body; qr_payload query required, fsos:package:<UUID>. Identity is not authorization. Foreign/missing package 404; malformed payload 409.')
async def resolve(request: Request, service: ServiceDep, qr_payload: Annotated[str, Query(min_length=1, max_length=100)]):
    return envelope(request, data=await service.resolve(qr_payload))


@router.get('/packages/{identifier}/delivery-context', response_model=PackageDeliveryContextEnvelope,
    description='Package.Read. UUID package; returns current package version/status and latest non-cancelled delivery manifest context for frontend school receiving auto-fill. Read-only; no timer mutation or receiving decision.')
async def delivery_context(request: Request, identifier: UUID, service: ServiceDep):
    return envelope(request, data=await service.delivery_context(identifier))


@router.get('/packages/{identifier}', response_model=PackageEnvelope,
    description='Package.Read. UUID path; no body/query. Live remaining_seconds/minutes and timer status; does not publish events or mutate persisted status. Legacy missing policy gives UNKNOWN, ineligible.')
async def detail(request: Request, identifier: UUID, service: ServiceDep):
    return envelope(request, data=await service.get(identifier))


@router.get('/production-batches/{identifier}/packaging', response_model=AllocationEnvelope,
    description='Package.Read. UUID production; no body/query. Actual/allocated/unallocated quantities, output UOM, frozen holding policy and current production version. Discard does not free allocated output.')
async def allocation(request: Request, identifier: UUID, service: ServiceDep):
    return envelope(request, data=await service.allocation(identifier))


@router.post('/packages/{identifier}/holding/start', response_model=PackageEnvelope,
    description='Holding.Start. UUID package + expected_version and optional device_uuid. Unexpired CREATED only; becomes PACKAGED. An active food sensor creates a HOLDING binding for subsequent temperature ingestion. Clock anchored to production.finished_at, never action time. Atomic version, registry, holding_log and holding.started.')
async def start(request: Request, identifier: UUID, payload: HoldingInput, service: ServiceDep):
    return envelope(request, data=await service.holding(identifier, payload, 'start'))


@router.post('/packages/{identifier}/holding/update', response_model=PackageEnvelope,
    description='Holding.Update. UUID package + expected_version. Refresh remaining time and materialize EXPIRED when deadline passed. No clock extension. Atomic version/registry/log/event; repeated expiry updates do not repeat holding.expired event. No background scheduler yet.')
async def refresh(request: Request, identifier: UUID, payload: HoldingInput, service: ServiceDep):
    return envelope(request, data=await service.holding(identifier, payload, 'update'))


@router.post('/packages/{identifier}/holding/finish', response_model=PackageEnvelope,
    description='Holding.Finish. UUID package + expected_version and outcome RELEASED or DISCARDED. Release only unexpired PACKAGED; discard any nonfinal package. Release ends holding station workflow but time continues counting for eligibility. No output reallocation on discard. Atomic version/registry/log/event.')
async def finish(request: Request, identifier: UUID, payload: HoldingFinishInput, service: ServiceDep):
    return envelope(request, data=await service.holding(identifier, payload, 'finish'))

