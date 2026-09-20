from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import AwareDatetime

from app.core.database.scope import ActorScope
from app.core.responses.envelope import Envelope, envelope
from app.modules.authentication.api.router import DatabaseDep, current_account
from app.modules.authentication.application.account_service import AuthenticatedAccount
from app.modules.authentication.infrastructure.authorization import PermissionDeniedError
from app.modules.telemetry.application.mqtt_event_service import MQTTEventService
from app.modules.telemetry.schemas.mqtt import MQTTEventPageEnvelope, MQTTTopicPageEnvelope

router = APIRouter(prefix='/mqtt', tags=['MQTT Discovery'], responses={
    400: {'model': Envelope, 'description': 'Invalid MQTT event filters'},
    401: {'model': Envelope, 'description': 'Missing/invalid bearer session'},
    403: {'model': Envelope, 'description': 'Device.Read permission missing'},
    503: {'model': Envelope, 'description': 'Authentication/database unavailable'},
})


async def mqtt_event_service(
    db: DatabaseDep,
    account: Annotated[AuthenticatedAccount, Depends(current_account, scope='function')],
):
    try:
        yield MQTTEventService(db, ActorScope(account.tenant_id, account.user_id))
    except PermissionDeniedError:
        raise HTTPException(403, 'Required permission is not granted') from None


ServiceDep = Annotated[MQTTEventService, Depends(mqtt_event_service, scope='function')]


@router.get(
    '/events', response_model=MQTTEventPageEnvelope,
    summary='Daftar event MQTT yang tersimpan',
    description=(
        'Bearer + Device.Read. Read-only discovery list from mqtt_message_log. '
        'This endpoint does not connect to MQTT, discover live topics, create devices, '
        'or mark messages processed.'
    ),
)
async def list_mqtt_events(
    request: Request,
    service: ServiceDep,
    topic: Annotated[str | None, Query(min_length=1, max_length=65535)] = None,
    processed: bool | None = None,
    since: Annotated[AwareDatetime | None, Query()] = None,
    until: Annotated[AwareDatetime | None, Query()] = None,
    offset: Annotated[int, Query(ge=0, le=2147483647)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    if since is not None and until is not None and since >= until:
        raise HTTPException(400, 'since must be earlier than until')
    return envelope(request, data=await service.list_events(
        topic=topic, processed=processed,
        since=since, until=until, offset=offset, limit=limit,
    ))


@router.get(
    '/topics', response_model=MQTTTopicPageEnvelope,
    summary='Daftar topic MQTT yang tersimpan',
    description='Bearer + Device.Read. Read-only distinct topics from mqtt_message_log; no broker connection or live discovery.',
)
async def list_mqtt_topics(
    request: Request,
    service: ServiceDep,
    topic_prefix: Annotated[str | None, Query(min_length=1, max_length=65535)] = None,
    offset: Annotated[int, Query(ge=0, le=2147483647)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    return envelope(request, data=await service.list_topics(
        topic_prefix=topic_prefix, offset=offset, limit=limit,
    ))
