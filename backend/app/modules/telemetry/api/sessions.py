from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import AwareDatetime

from app.core.database.scope import ActorScope, RecordNotFoundError
from app.core.responses.envelope import Envelope, envelope
from app.modules.authentication.api.router import DatabaseDep, current_account
from app.modules.authentication.application.account_service import AuthenticatedAccount
from app.modules.authentication.infrastructure.authorization import PermissionDeniedError
from app.modules.telemetry.application.lifecycle_service import (
    CompletionConflictError,
    TelemetryLifecycleService,
)
from app.modules.telemetry.schemas.sessions import (
    CloseSessionPayload,
    DeviceSessionEnvelope,
    DeviceSessionPageEnvelope,
)

router = APIRouter(prefix='/device-sessions', tags=['Device Sessions'], responses={
    400: {'model': Envelope, 'description': 'Invalid identifier, filters or invalid disconnection time'},
    401: {'model': Envelope, 'description': 'Missing/invalid/inactive bearer session'},
    403: {'model': Envelope, 'description': 'Required DeviceSession permission missing'},
    404: {'model': Envelope, 'description': 'Session unavailable in the authenticated tenant'},
    409: {'model': Envelope, 'description': 'Session ended at a different time'},
    503: {'model': Envelope, 'description': 'Authentication/database unavailable'},
    500: {'model': Envelope, 'description': 'Unexpected server error'},
})


async def session_service(db: DatabaseDep,
                        account: Annotated[AuthenticatedAccount, Depends(current_account, scope='function')]):
    try:
        yield TelemetryLifecycleService(db, ActorScope(account.tenant_id, account.user_id))
    except PermissionDeniedError:
        raise HTTPException(403, 'Required permission is not granted') from None
    except RecordNotFoundError:
        raise HTTPException(404, 'Telemetry record not found') from None
    except CompletionConflictError:
        raise HTTPException(409, 'Session already ended at a different time') from None
    except ValueError:
        raise HTTPException(400, 'Invalid session filters or disconnection time') from None


ServiceDep = Annotated[TelemetryLifecycleService, Depends(session_service, scope='function')]


@router.get('', response_model=DeviceSessionPageEnvelope, summary='Daftar sesi perangkat',
            description='Bearer + DeviceSession.Read. Effective is_open filter; connected_at descending then session_id. No body. since inclusive, until exclusive, timezone required.')
async def list_sessions(request: Request, service: ServiceDep,
                      device_uuid: Annotated[UUID | None, Query()] = None,
                      is_open: Annotated[Literal['true', 'false'] | None, Query()] = None,
                      since: Annotated[AwareDatetime | None, Query()] = None,
                      until: Annotated[AwareDatetime | None, Query()] = None,
                      offset: Annotated[int, Query(ge=0, le=2147483647)] = 0,
                      limit: Annotated[int, Query(ge=1, le=100)] = 20):
    return envelope(request, data=await service.list_sessions(
        device_uuid=device_uuid, is_open=None if is_open is None else is_open == 'true',
        since=since, until=until, offset=offset, limit=limit))


@router.get('/{session_id}', response_model=DeviceSessionEnvelope, summary='Detail sesi perangkat',
            description='Bearer + DeviceSession.Read. Effective status with original immutable snapshot. No body.')
async def get_session(request: Request, session_id: UUID, service: ServiceDep):
    return envelope(request, data=await service.get_session(session_id))


@router.post('/{session_id}/end', response_model=DeviceSessionEnvelope, summary='Tutup sesi perangkat',
             description='Bearer + DeviceSession.Close independent of Read. JSON disconnected_at ISO 8601 with timezone. Same timestamp retry returns original evidence; different timestamp 409. Does not mark device globally offline or open a reconnect session.')
async def close_session(request: Request, session_id: UUID, payload: CloseSessionPayload, service: ServiceDep):
    return envelope(request, data=await service.close_session(session_id, disconnected_at=payload.disconnected_at))
