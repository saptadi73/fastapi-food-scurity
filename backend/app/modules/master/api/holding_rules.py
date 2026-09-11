from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.exc import IntegrityError

from app.core.database.scope import ActorScope, RecordNotFoundError, VersionConflictError
from app.core.responses.envelope import Envelope, envelope
from app.modules.authentication.api.router import DatabaseDep, current_account
from app.modules.authentication.application.account_service import AuthenticatedAccount
from app.modules.authentication.infrastructure.authorization import PermissionDeniedError
from app.modules.master.application.rule_service import RuleService
from app.modules.master.schemas.holding_http import (
    HoldingEnvelope,
    HoldingHistoryEnvelope,
    HoldingPageEnvelope,
    HoldingRuleUpdate,
)
from app.modules.master.schemas.rules import HoldingRuleInput

router = APIRouter(prefix='/holding-rules', tags=['Holding Rules'], responses={
    400: {'model': Envelope, 'description': 'Invalid input or pagination'},
    401: {'model': Envelope, 'description': 'Missing/invalid/inactive bearer session'},
    403: {'model': Envelope, 'description': 'Required HoldingRule permission missing'},
    404: {'model': Envelope, 'description': 'Rule unavailable in the authenticated tenant'},
    409: {'model': Envelope, 'description': 'Duplicate category or version conflict'},
    503: {'model': Envelope, 'description': 'Authentication/database unavailable'},
    500: {'model': Envelope, 'description': 'Unexpected server error'},
})


async def holding_service(db: DatabaseDep,
                          account: Annotated[AuthenticatedAccount, Depends(current_account, scope='function')]):
    try:
        yield RuleService(db, ActorScope(account.tenant_id, account.user_id), 'holding')
    except PermissionDeniedError:
        raise HTTPException(403, 'Required permission is not granted') from None
    except RecordNotFoundError:
        raise HTTPException(404, 'Rule not found') from None
    except VersionConflictError:
        raise HTTPException(409, 'Rule changed; reload before retrying') from None
    except IntegrityError as exc:
        if getattr(exc.orig, 'sqlstate', None) == '23505':
            raise HTTPException(409, 'Food category already exists in this tenant') from None
        raise
    except ValueError:
        raise HTTPException(400, 'Invalid holding rule input') from None


ServiceDep = Annotated[RuleService, Depends(holding_service, scope='function')]
Offset = Annotated[int, Query(ge=0, le=2147483647)]
Limit = Annotated[int, Query(ge=1, le=100)]


@router.get('', response_model=HoldingPageEnvelope, summary='Daftar holding rule',
            description='Bearer + HoldingRule.Read. Tenant from session. Newest first; offset/limit pagination. No request body.')
async def list_rules(request: Request, service: ServiceDep, offset: Offset = 0, limit: Limit = 20):
    return envelope(request, data={'items': await service.list(offset=offset, limit=limit), 'offset': offset, 'limit': limit})


@router.post('', response_model=HoldingEnvelope, status_code=201, summary='Buat holding rule',
             description='Bearer + HoldingRule.Write. Warning <= maximum <= discard. Initial revision committed atomically; does not start holding engine.')
async def create_rule(request: Request, payload: HoldingRuleInput, service: ServiceDep):
    return envelope(request, code=201, data=await service.create(payload.model_dump()))


@router.get('/{rule_id}', response_model=HoldingEnvelope, summary='Detail holding rule',
            description='Bearer + HoldingRule.Read. Missing/deleted/other-tenant rules return the same 404. No body.')
async def get_rule(request: Request, rule_id: UUID, service: ServiceDep):
    return envelope(request, data=await service.get(rule_id))


@router.put('/{rule_id}', response_model=HoldingEnvelope, summary='Ganti definisi holding rule',
            description='Bearer + HoldingRule.Write. Full replacement plus expected_version. Stale version is 409; revision recorded atomically.')
async def update_rule(request: Request, rule_id: UUID, payload: HoldingRuleUpdate, service: ServiceDep):
    return envelope(request, data=await service.save(rule_id, payload.model_dump(exclude={'expected_version'}), expected_version=payload.expected_version))


@router.get('/{rule_id}/history', response_model=HoldingHistoryEnvelope, summary='Riwayat holding rule',
            description='Bearer + HoldingRule.Read. Descending version, offset/limit. Immutable snapshots; no body.')
async def history(request: Request, rule_id: UUID, service: ServiceDep, offset: Offset = 0, limit: Limit = 20):
    return envelope(request, data={'items': await service.history(rule_id, offset=offset, limit=limit), 'offset': offset, 'limit': limit})
