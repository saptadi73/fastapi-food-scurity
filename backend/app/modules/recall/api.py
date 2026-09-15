from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.exc import IntegrityError

from app.core.database.scope import ActorScope, RecordNotFoundError, VersionConflictError
from app.core.responses.envelope import Envelope, envelope
from app.modules.authentication.api.router import DatabaseDep, current_account
from app.modules.authentication.application.account_service import AuthenticatedAccount
from app.modules.authentication.infrastructure.authorization import PermissionDeniedError
from app.modules.recall.application import RecallConflictError, RecallService
from app.modules.recall.schemas import (
    RecallCloseInput,
    RecallEnvelope,
    RecallExecuteInput,
    RecallInput,
    RecallPageEnvelope,
    RecallWithdrawalEnvelope,
    RecallWithdrawalInput,
    RecallWithdrawalPageEnvelope,
)

router = APIRouter(prefix='/recalls', tags=['Recall'], responses={
    400: {'model': Envelope, 'description': 'Invalid payload, path or query'},
    401: {'model': Envelope, 'description': 'Invalid bearer session'},
    403: {'model': Envelope, 'description': 'Required Recall permission is not granted'},
    404: {'model': Envelope, 'description': 'Recall not found in tenant'},
    409: {'model': Envelope, 'description': 'Invalid production batch, stale version or transition'},
    500: {'model': Envelope, 'description': 'Unexpected server error'},
    503: {'model': Envelope, 'description': 'Authentication/database unavailable'},
})


async def service_dependency(db: DatabaseDep,
    account: Annotated[AuthenticatedAccount, Depends(current_account, scope='function')]):
    try:
        yield RecallService(db, ActorScope(account.tenant_id, account.user_id))
    except PermissionDeniedError:
        raise HTTPException(403, 'Required Recall permission is not granted') from None
    except RecordNotFoundError:
        raise HTTPException(404, 'Recall not found') from None
    except VersionConflictError:
        raise HTTPException(409, 'Recall changed; reload before retrying') from None
    except RecallConflictError as exc:
        raise HTTPException(409, str(exc)) from None
    except IntegrityError as exc:
        if getattr(exc.orig, 'sqlstate', None) == '23503':
            raise HTTPException(409, 'Recall reference unavailable') from None
        raise


ServiceDep = Annotated[RecallService, Depends(service_dependency, scope='function')]
Offset = Annotated[int, Query(ge=0, le=2147483647)]
Limit = Annotated[int, Query(ge=1, le=100)]


@router.post('', status_code=201, response_model=RecallEnvelope,
    description='Recall.Execute. Start recall for one production batch. Server started_at, registry RECALL, RECALLED edge, affected package snapshot/movements and stored event are atomic. Does not change package status.')
async def create_recall(request: Request, payload: RecallInput, service: ServiceDep):
    return envelope(request, code=201, data=await service.create(payload))


@router.get('', response_model=RecallPageEnvelope,
    description='Recall.Read. No body; tenant recalls with affected package snapshots, optional production_batch_id/open_only filters, created_at/ID descending, offset pagination.')
async def list_recalls(request: Request, service: ServiceDep, offset: Offset = 0, limit: Limit = 20,
    production_batch_id: UUID | None = None, open_only: bool | None = None):
    return envelope(request, data=await service.list(
        offset=offset, limit=limit, production_batch_id=production_batch_id, open_only=open_only,
    ))


@router.get('/{identifier}', response_model=RecallEnvelope,
    description='Recall.Read. UUID path, no body/query. Detail includes current package snapshots for the recalled production batch.')
async def get_recall(request: Request, identifier: UUID, service: ServiceDep):
    return envelope(request, data=await service.get(identifier))


@router.post('/{identifier}/withdrawals', status_code=201, response_model=RecallWithdrawalEnvelope,
    description='Recall.Execute. Append physical withdrawal evidence for an open recall. Optional package_id must belong to the recalled production batch. Writes RECALL movement and stored event.')
async def create_withdrawal(request: Request, identifier: UUID, payload: RecallWithdrawalInput, service: ServiceDep):
    return envelope(request, code=201, data=await service.withdrawal(identifier, payload))


@router.get('/{identifier}/withdrawals', response_model=RecallWithdrawalPageEnvelope,
    description='Recall.Read. List physical withdrawal evidence for one recall, newest first, optionally filtered by package_id.')
async def list_withdrawals(request: Request, identifier: UUID, service: ServiceDep, offset: Offset = 0,
    limit: Limit = 20, package_id: UUID | None = None):
    return envelope(request, data=await service.withdrawals(
        identifier, offset=offset, limit=limit, package_id=package_id))


@router.post('/{identifier}/execute', response_model=RecallEnvelope,
    description='Recall.Execute. Execute an open recall with expected_version. Marks nonterminal affected packages RECALLED, writes package->recall edges, movements and stored event. Terminal consumed/discarded/rejected packages stay terminal.')
async def execute_recall(request: Request, identifier: UUID, payload: RecallExecuteInput, service: ServiceDep):
    return envelope(request, data=await service.execute(identifier, payload))


@router.post('/{identifier}/close', response_model=RecallEnvelope,
    description='Recall.Execute. Close an open recall with expected_version. Server completed_at and stored event are atomic. Does not change package status or send notifications.')
async def close_recall(request: Request, identifier: UUID, payload: RecallCloseInput, service: ServiceDep):
    return envelope(request, data=await service.close(identifier, payload))
