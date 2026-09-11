from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.exc import IntegrityError

from app.core.database.scope import ActorScope, RecordNotFoundError, VersionConflictError
from app.core.responses.envelope import Envelope, envelope
from app.modules.authentication.api.router import DatabaseDep, current_account
from app.modules.authentication.application.account_service import AuthenticatedAccount
from app.modules.authentication.infrastructure.authorization import PermissionDeniedError
from app.modules.master.application.rule_service import RuleService, RuleStateError
from app.modules.master.schemas.alarm_http import (
    AlarmEnvelope,
    AlarmHistoryEnvelope,
    AlarmPageEnvelope,
    AlarmRuleActivation,
    AlarmRuleUpdate,
)
from app.modules.master.schemas.rules import AlarmRuleInput

router = APIRouter(prefix='/alarm-rules', tags=['Alarm Rules'], responses={
    400: {'model': Envelope, 'description': 'Invalid input or pagination'},
    401: {'model': Envelope, 'description': 'Missing/invalid/inactive bearer session'},
    403: {'model': Envelope, 'description': 'Required AlarmRule permission missing'},
    404: {'model': Envelope, 'description': 'Rule unavailable in the authenticated tenant'},
    409: {'model': Envelope, 'description': 'Duplicate code, active definition or version conflict'},
    503: {'model': Envelope, 'description': 'Authentication/database unavailable'},
    500: {'model': Envelope, 'description': 'Unexpected server error'},
})


async def alarm_service(db: DatabaseDep,
                          account: Annotated[AuthenticatedAccount, Depends(current_account, scope='function')]):
    try:
        yield RuleService(db, ActorScope(account.tenant_id, account.user_id), 'alarm')
    except PermissionDeniedError:
        raise HTTPException(403, 'Required permission is not granted') from None
    except RecordNotFoundError:
        raise HTTPException(404, 'Rule not found') from None
    except VersionConflictError:
        raise HTTPException(409, 'Rule changed; reload before retrying') from None
    except RuleStateError:
        raise HTTPException(409, 'Disable alarm rule before changing its definition') from None
    except IntegrityError as exc:
        if getattr(exc.orig, 'sqlstate', None) == '23505':
            raise HTTPException(409, 'Rule code already exists in this tenant') from None
        raise
    except ValueError:
        raise HTTPException(400, 'Invalid alarm rule input') from None


ServiceDep = Annotated[RuleService, Depends(alarm_service, scope='function')]
Offset = Annotated[int, Query(ge=0, le=2147483647)]
Limit = Annotated[int, Query(ge=1, le=100)]


@router.get('', response_model=AlarmPageEnvelope, summary='Daftar alarm rule',
            description='Bearer + AlarmRule.Read. Tenant from session. Newest first; offset/limit pagination. No request body.')
async def list_rules(request: Request, service: ServiceDep, offset: Offset = 0, limit: Limit = 20):
    return envelope(request, data={'items': await service.list(offset=offset, limit=limit), 'offset': offset, 'limit': limit})


@router.post('', response_model=AlarmEnvelope, status_code=201, summary='Buat alarm rule',
             description='Bearer + AlarmRule.Write. DSL v1 required; created disabled. Initial revision committed atomically; does not start alarm engine.')
async def create_rule(request: Request, payload: AlarmRuleInput, service: ServiceDep):
    return envelope(request, code=201, data=await service.create(payload.model_dump()))


@router.get('/{rule_id}', response_model=AlarmEnvelope, summary='Detail alarm rule',
            description='Bearer + AlarmRule.Read. Missing/deleted/other-tenant rules return the same 404. No body.')
async def get_rule(request: Request, rule_id: UUID, service: ServiceDep):
    return envelope(request, data=await service.get(rule_id))


@router.put('/{rule_id}', response_model=AlarmEnvelope, summary='Ganti definisi alarm rule',
            description='Bearer + AlarmRule.Write. Full replacement plus expected_version. Rule must be disabled. Stale version is 409; revision recorded atomically.')
async def update_rule(request: Request, rule_id: UUID, payload: AlarmRuleUpdate, service: ServiceDep):
    return envelope(request, data=await service.save(rule_id, payload.model_dump(exclude={'expected_version'}), expected_version=payload.expected_version))


@router.get('/{rule_id}/history', response_model=AlarmHistoryEnvelope, summary='Riwayat alarm rule',
            description='Bearer + AlarmRule.Read. Descending version, offset/limit. Immutable snapshots; no body.')
async def history(request: Request, rule_id: UUID, service: ServiceDep, offset: Offset = 0, limit: Limit = 20):
    return envelope(request, data={'items': await service.history(rule_id, offset=offset, limit=limit), 'offset': offset, 'limit': limit})


@router.put('/{rule_id}/enabled', response_model=AlarmEnvelope, summary='Aktifkan/nonaktifkan alarm rule',
            description='Bearer + AlarmRule.Activate. Boolean enabled and expected_version required. Revalidates DSL when enabling. Same state/version is a no-op. No engine execution or event publication.')
async def set_enabled(request: Request, rule_id: UUID, payload: AlarmRuleActivation, service: ServiceDep):
    return envelope(request, data=await service.set_enabled(rule_id, payload.enabled, expected_version=payload.expected_version))
