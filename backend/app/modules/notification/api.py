from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.database.scope import ActorScope, RecordNotFoundError, VersionConflictError
from app.core.responses.envelope import Envelope, envelope
from app.modules.authentication.api.router import DatabaseDep, current_account
from app.modules.authentication.application.account_service import AuthenticatedAccount
from app.modules.authentication.infrastructure.authorization import PermissionDeniedError
from app.modules.notification.application import NotificationConflictError, NotificationService
from app.modules.notification.schemas import (
    NotificationChannel,
    NotificationEnvelope,
    NotificationMarkFailedInput,
    NotificationMarkSentInput,
    NotificationPageEnvelope,
    NotificationStatus,
)

router = APIRouter(prefix='/notifications', tags=['Notifications'], responses={
    400: {'model': Envelope, 'description': 'Invalid payload, path or query'},
    401: {'model': Envelope, 'description': 'Invalid bearer session'},
    403: {'model': Envelope, 'description': 'Required Notification permission is not granted'},
    404: {'model': Envelope, 'description': 'Notification not found in tenant'},
    409: {'model': Envelope, 'description': 'Stale version or invalid notification transition'},
    500: {'model': Envelope, 'description': 'Unexpected server error'},
    503: {'model': Envelope, 'description': 'Authentication/database unavailable'},
})


async def service_dependency(db: DatabaseDep,
    account: Annotated[AuthenticatedAccount, Depends(current_account, scope='function')]):
    try:
        yield NotificationService(db, ActorScope(account.tenant_id, account.user_id))
    except PermissionDeniedError:
        raise HTTPException(403, 'Required Notification permission is not granted') from None
    except RecordNotFoundError:
        raise HTTPException(404, 'Notification not found') from None
    except VersionConflictError:
        raise HTTPException(409, 'Notification changed; reload before retrying') from None
    except NotificationConflictError as exc:
        raise HTTPException(409, str(exc)) from None


ServiceDep = Annotated[NotificationService, Depends(service_dependency, scope='function')]
Offset = Annotated[int, Query(ge=0, le=2147483647)]
Limit = Annotated[int, Query(ge=1, le=100)]


@router.get('', response_model=NotificationPageEnvelope,
    description='Notification.Read. Tenant notification outbox, newest first. No body. Optional status/channel/entity filters and offset pagination.')
async def list_notifications(request: Request, service: ServiceDep, offset: Offset = 0, limit: Limit = 20,
    status: Annotated[NotificationStatus | None, Query()] = None,
    channel: Annotated[NotificationChannel | None, Query()] = None,
    entity_type: Annotated[str | None, Query(min_length=1, max_length=50)] = None,
    entity_uuid: Annotated[UUID | None, Query()] = None):
    return envelope(request, data=await service.list(
        offset=offset, limit=limit, status=status, channel=channel,
        entity_type=entity_type, entity_uuid=entity_uuid,
    ))


@router.post('/{identifier}/mark-sent', response_model=NotificationEnvelope,
    description='Notification.Dispatch. Mark one pending/failed notification as SENT with expected_version. Does not contact external providers.')
async def mark_sent(request: Request, identifier: UUID, payload: NotificationMarkSentInput, service: ServiceDep):
    return envelope(request, data=await service.mark_sent(identifier, payload))


@router.post('/{identifier}/mark-failed', response_model=NotificationEnvelope,
    description='Notification.Dispatch. Mark one pending/failed notification as FAILED with expected_version and failure_reason. Does not retry automatically.')
async def mark_failed(request: Request, identifier: UUID, payload: NotificationMarkFailedInput, service: ServiceDep):
    return envelope(request, data=await service.mark_failed(identifier, payload))
