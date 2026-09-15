from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.database.scope import ActorScope, RecordNotFoundError
from app.core.responses.envelope import Envelope, envelope
from app.modules.authentication.api.router import DatabaseDep, current_account
from app.modules.authentication.application.account_service import AuthenticatedAccount
from app.modules.authentication.infrastructure.authorization import PermissionDeniedError
from app.modules.traceability.application.trace_service import TraceabilityService
from app.modules.traceability.schemas import (
    AssetEnvelope,
    AssetPassportEnvelope,
    ImpactEnvelope,
    MovementPageEnvelope,
    RelationshipPageEnvelope,
    TraceGraphEnvelope,
)

router = APIRouter(prefix='/traceability/assets', tags=['Traceability'], responses={
    400: {'model': Envelope, 'description': 'Invalid path or query'},
    401: {'model': Envelope, 'description': 'Invalid bearer session'},
    403: {'model': Envelope, 'description': 'Required Traceability permission is not granted'},
    404: {'model': Envelope, 'description': 'Asset not found in tenant'},
    500: {'model': Envelope, 'description': 'Unexpected server error'},
    503: {'model': Envelope, 'description': 'Authentication/database unavailable'},
})


async def service_dependency(db: DatabaseDep,
    account: Annotated[AuthenticatedAccount, Depends(current_account, scope='function')]):
    try:
        yield TraceabilityService(db, ActorScope(account.tenant_id, account.user_id))
    except PermissionDeniedError:
        raise HTTPException(403, 'Required Traceability permission is not granted') from None
    except RecordNotFoundError:
        raise HTTPException(404, 'Asset not found') from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


ServiceDep = Annotated[TraceabilityService, Depends(service_dependency, scope='function')]
Offset = Annotated[int, Query(ge=0, le=2147483647)]
Limit = Annotated[int, Query(ge=1, le=100)]


@router.get('/{asset_uuid}', response_model=AssetEnvelope,
    description='Traceability.Read. Detail digital asset by registry asset_uuid. No body/query.')
async def get_asset(request: Request, asset_uuid: UUID, service: ServiceDep):
    return envelope(request, data=await service.asset(asset_uuid))


@router.get('/{asset_uuid}/relationships', response_model=RelationshipPageEnvelope,
    description='Traceability.Read. Direct parent/child edges for asset_uuid. direction=children returns outgoing edges; parents returns incoming edges.')
async def get_relationships(request: Request, asset_uuid: UUID, service: ServiceDep,
    direction: Literal['children', 'parents'] = 'children', offset: Offset = 0, limit: Limit = 20):
    return envelope(request, data=await service.relationships(
        asset_uuid, direction=direction, offset=offset, limit=limit,
    ))


@router.get('/{asset_uuid}/movements', response_model=MovementPageEnvelope,
    description='Traceability.Read. Movement timeline for asset_uuid, newest first. Read-only evidence; no replay or publisher.')
async def get_movements(request: Request, asset_uuid: UUID, service: ServiceDep,
    offset: Offset = 0, limit: Limit = 20):
    return envelope(request, data=await service.movements(asset_uuid, offset=offset, limit=limit))


@router.get('/{asset_uuid}/passport', response_model=AssetPassportEnvelope,
    description='Traceability.Read. Read-only asset passport: asset snapshot, direct parent/child edges and latest movement timeline.')
async def get_passport(request: Request, asset_uuid: UUID, service: ServiceDep):
    return envelope(request, data=await service.passport(asset_uuid))


@router.get('/{asset_uuid}/impact', response_model=ImpactEnvelope,
    description='Traceability.Read. Downstream impact analysis from asset_uuid using forward traversal. Includes affected counts and package/complaint/recall subsets.')
async def get_impact(request: Request, asset_uuid: UUID, service: ServiceDep,
    depth: Annotated[int, Query(ge=1, le=6)] = 6,
    limit: Annotated[int, Query(ge=1, le=200)] = 200):
    return envelope(request, data=await service.impact(asset_uuid, depth=depth, limit=limit))


@router.get('/{asset_uuid}/traverse', response_model=TraceGraphEnvelope,
    description='Traceability.Read. Bounded graph traversal from asset_uuid. direction=forward follows parent->child; backward follows child->parent.')
async def traverse(request: Request, asset_uuid: UUID, service: ServiceDep,
    direction: Literal['forward', 'backward'] = 'forward',
    depth: Annotated[int, Query(ge=1, le=6)] = 3,
    limit: Annotated[int, Query(ge=1, le=200)] = 100):
    return envelope(request, data=await service.traverse(
        asset_uuid, direction=direction, depth=depth, limit=limit,
    ))
