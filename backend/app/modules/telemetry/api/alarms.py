from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import AwareDatetime

from app.core.database.scope import ActorScope, RecordNotFoundError
from app.core.responses.envelope import Envelope, envelope
from app.modules.authentication.api.router import DatabaseDep, current_account
from app.modules.authentication.application.account_service import AuthenticatedAccount
from app.modules.authentication.infrastructure.authorization import PermissionDeniedError
from app.modules.telemetry.application.lifecycle_service import TelemetryLifecycleService
from app.modules.telemetry.schemas.alarms import AlarmEnvelope, AlarmPageEnvelope

router = APIRouter(prefix='/alarms', tags=['Telemetry Alarms'], responses={
    400: {'model': Envelope, 'description': 'Invalid identifier, filters or future alarm observation'},
    401: {'model': Envelope, 'description': 'Missing/invalid/inactive bearer session'},
    403: {'model': Envelope, 'description': 'Required Alarm permission missing'},
    404: {'model': Envelope, 'description': 'Alarm unavailable in the authenticated tenant'},
    503: {'model': Envelope, 'description': 'Authentication/database unavailable'},
    500: {'model': Envelope, 'description': 'Unexpected server error'},
})


async def alarm_service(db: DatabaseDep,
                        account: Annotated[AuthenticatedAccount, Depends(current_account, scope='function')]):
    try:
        yield TelemetryLifecycleService(db, ActorScope(account.tenant_id, account.user_id))
    except PermissionDeniedError:
        raise HTTPException(403, 'Required permission is not granted') from None
    except RecordNotFoundError:
        raise HTTPException(404, 'Telemetry record not found') from None
    except ValueError:
        raise HTTPException(400, 'Invalid alarm filters or observation time') from None


ServiceDep = Annotated[TelemetryLifecycleService, Depends(alarm_service, scope='function')]


@router.get('', response_model=AlarmPageEnvelope, summary='Daftar kejadian alarm',
            description='Bearer + Alarm.Read. Effective acknowledgment filter; recorded_at descending then alarm_id. No body. since inclusive, until exclusive, timezone required.')
async def list_alarms(request: Request, service: ServiceDep,
                      device_uuid: Annotated[UUID | None, Query()] = None,
                      acknowledged: Annotated[Literal['true', 'false'] | None, Query()] = None,
                      since: Annotated[AwareDatetime | None, Query()] = None,
                      until: Annotated[AwareDatetime | None, Query()] = None,
                      offset: Annotated[int, Query(ge=0, le=2147483647)] = 0,
                      limit: Annotated[int, Query(ge=1, le=100)] = 20):
    return envelope(request, data=await service.list_alarms(
        device_uuid=device_uuid, acknowledged=None if acknowledged is None else acknowledged == 'true',
        since=since, until=until, offset=offset, limit=limit))


@router.get('/{alarm_id}', response_model=AlarmEnvelope, summary='Detail kejadian alarm',
            description='Bearer + Alarm.Read. Effective status with original immutable snapshot. No body.')
async def get_alarm(request: Request, alarm_id: UUID, service: ServiceDep):
    return envelope(request, data=await service.get_alarm(alarm_id))


@router.post('/{alarm_id}/acknowledgment', response_model=AlarmEnvelope, summary='Akui kejadian alarm',
             description='Bearer + Alarm.Acknowledge independent of Read. No body. Server actor/time; retries return first evidence, including imported acknowledged snapshots. No event publication.')
async def acknowledge(request: Request, alarm_id: UUID, service: ServiceDep):
    if await request.body():
        raise HTTPException(400, 'Request body must be empty')
    return envelope(request, data=await service.acknowledge(alarm_id))
