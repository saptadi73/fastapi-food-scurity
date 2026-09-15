from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.exc import IntegrityError

from app.core.database.scope import ActorScope, RecordNotFoundError, VersionConflictError
from app.core.responses.envelope import Envelope, envelope
from app.modules.authentication.api.router import DatabaseDep, current_account
from app.modules.authentication.application.account_service import AuthenticatedAccount
from app.modules.authentication.infrastructure.authorization import PermissionDeniedError
from app.modules.fleet.application.delivery_service import DeliveryConflictError, DeliveryService
from app.modules.fleet.schemas.delivery import (
    DeliveryAction,
    DeliveryEnvelope,
    DeliveryInput,
    DeliveryPackageDestinationPageEnvelope,
    DeliveryPackageVehiclePageEnvelope,
    DeliveryPageEnvelope,
    DeliveryTrackingEnvelope,
    DepartureInput,
)

router = APIRouter(prefix='/deliveries', tags=['Delivery'], responses={
    400: {'model': Envelope, 'description': 'Invalid payload, path or query'},
    401: {'model': Envelope, 'description': 'Invalid bearer session'},
    403: {'model': Envelope, 'description': 'Required permission is not granted'},
    404: {'model': Envelope, 'description': 'Delivery not found in tenant'},
    409: {'model': Envelope, 'description': 'Stale version, duplicate batch/QR, invalid parent or transition'},
    500: {'model': Envelope, 'description': 'Unexpected server error'},
    503: {'model': Envelope, 'description': 'Authentication/database unavailable'},
})


async def service_dependency(db: DatabaseDep,
    account: Annotated[AuthenticatedAccount, Depends(current_account, scope='function')]):
    try:
        yield DeliveryService(db, ActorScope(account.tenant_id, account.user_id))
    except PermissionDeniedError:
        raise HTTPException(403, 'Required permission is not granted') from None
    except RecordNotFoundError:
        raise HTTPException(404, 'Delivery not found') from None
    except VersionConflictError:
        raise HTTPException(409, 'Delivery or package changed; reload before retrying') from None
    except DeliveryConflictError as exc:
        raise HTTPException(409, str(exc)) from None
    except IntegrityError as exc:
        if getattr(exc.orig, 'sqlstate', None) == '23505':
            raise HTTPException(409, 'Delivery manifest conflict') from None
        if getattr(exc.orig, 'sqlstate', None) == '23503':
            raise HTTPException(409, 'Delivery reference unavailable') from None
        raise


ServiceDep = Annotated[DeliveryService, Depends(service_dependency, scope='function')]
Offset = Annotated[int, Query(ge=0, le=2147483647)]
Limit = Annotated[int, Query(ge=1, le=100)]


@router.post('', status_code=201, response_model=DeliveryEnvelope,
    description='Delivery.Write. Origin kitchen, vehicle, driver and 1..100 unique package/school/version lines. Active same-tenant parents, school/package origin match, released unexpired packages. Reserves package/vehicle/driver; atomic package ALLOCATED/version, manifest, registry and delivery.created. No movement until departure.')
async def create(request: Request, payload: DeliveryInput, service: ServiceDep):
    return envelope(request, code=201, data=await service.create(payload))


@router.get('', response_model=DeliveryPageEnvelope,
    description='Delivery.Read. No body; tenant nondeleted headers, optional kitchen_id/vehicle/driver/status AND filters; created_at/ID descending, offset/limit with nullable next_offset.')
async def listing(request: Request, service: ServiceDep, offset: Offset = 0, limit: Limit = 20,
    kitchen_id: UUID | None = None, vehicle: UUID | None = None, driver: UUID | None = None,
    status: Literal['CREATED', 'IN_TRANSIT', 'COMPLETED', 'CANCELLED'] | None = None):
    return envelope(request, data=await service.list(offset=offset, limit=limit, kitchen_id=kitchen_id, vehicle=vehicle, driver=driver, status=status))


@router.get('/packages/by-vehicle', response_model=DeliveryPackageVehiclePageEnvelope,
    description='Delivery.Read. No body; package counts and quantities grouped by vehicle, optional vehicle/status filters, offset/limit. UOM is null when grouped packages mix output units.')
async def packages_by_vehicle(request: Request, service: ServiceDep, offset: Offset = 0, limit: Limit = 20,
    vehicle: UUID | None = None, status: Literal['CREATED', 'IN_TRANSIT', 'COMPLETED', 'CANCELLED'] | None = None):
    return envelope(request, data=await service.package_summary(
        group_by='vehicle', offset=offset, limit=limit, vehicle=vehicle, status=status))


@router.get('/packages/by-destination', response_model=DeliveryPackageDestinationPageEnvelope,
    description='Delivery.Read. No body; package counts and quantities grouped by destination school, optional school_id/status filters, offset/limit. UOM is null when grouped packages mix output units.')
async def packages_by_destination(request: Request, service: ServiceDep, offset: Offset = 0, limit: Limit = 20,
    school_id: UUID | None = None, status: Literal['CREATED', 'IN_TRANSIT', 'COMPLETED', 'CANCELLED'] | None = None):
    return envelope(request, data=await service.package_summary(
        group_by='school_id', offset=offset, limit=limit, school_id=school_id, status=status))


@router.get('/{identifier}/tracking', response_model=DeliveryTrackingEnvelope,
    description='Delivery.Read. UUID delivery; latest GPS for vehicle, latest temperature from assigned GPS device if any, estimated remaining distance/time to farthest destination. Read-only; no telemetry ingestion or realtime subscription.')
async def tracking(request: Request, identifier: UUID, service: ServiceDep):
    return envelope(request, data=await service.tracking(identifier))


@router.get('/{identifier}', response_model=DeliveryEnvelope,
    description='Delivery.Read. UUID path; no body/query. Manifest sorted by package UUID; nested package contains current timer and state, not historical snapshot. Foreign/missing/deleted 404.')
async def detail(request: Request, identifier: UUID, service: ServiceDep):
    return envelope(request, data=await service.get(identifier))


@router.post('/{identifier}/depart', response_model=DeliveryEnvelope,
    description='Delivery.Depart. CREATED only, delivery expected_version plus optional timezone-aware future estimated_arrival_time. When omitted, ETA is estimated from route coordinates. Rechecks active parents/assignment, allocated packages, holding and ETA strictly before all expiry deadlines. Atomic IN_TRANSIT, package versions, LOADED edges, VEHICLE_LOADING movements, registry and event.')
async def depart(request: Request, identifier: UUID, payload: DepartureInput, service: ServiceDep):
    return envelope(request, data=await service.transition(identifier, payload, 'depart'))


@router.post('/{identifier}/complete', response_model=DeliveryEnvelope,
    description='Delivery.Complete. IN_TRANSIT only, expected_version. Confirms all manifest packages physically arrived at their assigned schools, server arrival timestamp; packages DELIVERED, edges and movement. Permits expiry/late arrival and inactive parents; does not assert food accepted, create school receiving or reset timer.')
async def complete(request: Request, identifier: UUID, payload: DeliveryAction, service: ServiceDep):
    return envelope(request, data=await service.transition(identifier, payload, 'complete'))


@router.post('/{identifier}/cancel', response_model=DeliveryEnvelope,
    description='Delivery.Cancel. CREATED only, expected_version. Releases resource reservations; packages RELEASED if unexpired else EXPIRED. Preserves manifest; no movement or clock reset. No in-transit cancellation or manifest edit.')
async def cancel(request: Request, identifier: UUID, payload: DeliveryAction, service: ServiceDep):
    return envelope(request, data=await service.transition(identifier, payload, 'cancel'))
