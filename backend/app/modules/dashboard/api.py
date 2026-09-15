from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.database.scope import ActorScope
from app.core.responses.envelope import Envelope, envelope
from app.modules.authentication.api.router import DatabaseDep, current_account
from app.modules.authentication.application.account_service import AuthenticatedAccount
from app.modules.authentication.infrastructure.authorization import PermissionDeniedError
from app.modules.dashboard.schemas import (
    DashboardFleetEnvelope,
    DashboardHoldingEnvelope,
    DashboardHomeEnvelope,
    DashboardNotificationEnvelope,
    DashboardRecallEnvelope,
    DashboardStorageEnvelope,
    DashboardStorageTemperaturePageEnvelope,
)
from app.modules.dashboard.service import DashboardService

router = APIRouter(prefix='/dashboard', tags=['Dashboard'], responses={
    401: {'model': Envelope, 'description': 'Invalid bearer session'},
    403: {'model': Envelope, 'description': 'Required Dashboard permission is not granted'},
    500: {'model': Envelope, 'description': 'Unexpected server error'},
    503: {'model': Envelope, 'description': 'Authentication/database unavailable'},
})


async def service_dependency(db: DatabaseDep,
    account: Annotated[AuthenticatedAccount, Depends(current_account, scope='function')]):
    try:
        yield DashboardService(db, ActorScope(account.tenant_id, account.user_id))
    except PermissionDeniedError:
        raise HTTPException(403, 'Required Dashboard permission is not granted') from None


ServiceDep = Annotated[DashboardService, Depends(service_dependency, scope='function')]
Offset = Annotated[int, Query(ge=0, le=2147483647)]
Limit = Annotated[int, Query(ge=1, le=100)]


@router.get('/home', response_model=DashboardHomeEnvelope,
    description='Dashboard.Read. Tenant operational counters for home dashboard. Read-only snapshot; no event, cache or cross-tenant data.')
async def home(request: Request, service: ServiceDep):
    return envelope(request, data=await service.home())


@router.get('/storage', response_model=DashboardStorageEnvelope,
    description='Dashboard.Read. Tenant storage counters. Read-only snapshot; no event, cache or cross-tenant data.')
async def storage(request: Request, service: ServiceDep):
    return envelope(request, data=await service.storage())


@router.get('/storage-temperatures', response_model=DashboardStorageTemperaturePageEnvelope,
    description='Dashboard.Read. Latest temperature per active storage with threshold status OK/LOW/HIGH/UNSUPPORTED_UNIT/NO_DATA. Read-only snapshot; no MQTT/WebSocket/event.')
async def storage_temperatures(request: Request, service: ServiceDep, offset: Offset = 0, limit: Limit = 20):
    return envelope(request, data=await service.storage_temperatures(offset=offset, limit=limit))


@router.get('/fleet', response_model=DashboardFleetEnvelope,
    description='Dashboard.Read. Tenant fleet counters. Read-only snapshot; no event, cache or cross-tenant data.')
async def fleet(request: Request, service: ServiceDep):
    return envelope(request, data=await service.fleet())


@router.get('/holding', response_model=DashboardHoldingEnvelope,
    description='Dashboard.Read. Tenant holding counters. Read-only snapshot; no event, cache or cross-tenant data.')
async def holding(request: Request, service: ServiceDep):
    return envelope(request, data=await service.holding())


@router.get('/recall', response_model=DashboardRecallEnvelope,
    description='Dashboard.Read. Tenant recall counters. Read-only snapshot; no event, cache or cross-tenant data.')
async def recall(request: Request, service: ServiceDep):
    return envelope(request, data=await service.recall())


@router.get('/notifications', response_model=DashboardNotificationEnvelope,
    description='Dashboard.Read. Tenant notification outbox counters by status/channel. Read-only snapshot; no external dispatch, event or realtime subscription.')
async def notifications(request: Request, service: ServiceDep):
    return envelope(request, data=await service.notifications())
