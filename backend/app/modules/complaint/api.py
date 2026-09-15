from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.exc import IntegrityError

from app.core.database.scope import ActorScope, RecordNotFoundError
from app.core.responses.envelope import Envelope, envelope
from app.modules.authentication.api.router import DatabaseDep, current_account
from app.modules.authentication.application.account_service import AuthenticatedAccount
from app.modules.authentication.infrastructure.authorization import PermissionDeniedError
from app.modules.complaint.application import ComplaintConflictError, ComplaintService
from app.modules.complaint.schemas import (
    ComplaintEnvelope,
    ComplaintInput,
    ComplaintPageEnvelope,
    ComplaintReportEnvelope,
    ComplaintReportPageEnvelope,
)

router = APIRouter(prefix='/complaints', tags=['Complaint'], responses={
    400: {'model': Envelope, 'description': 'Invalid payload, path or query'},
    401: {'model': Envelope, 'description': 'Invalid bearer session'},
    403: {'model': Envelope, 'description': 'Required Complaint permission is not granted'},
    404: {'model': Envelope, 'description': 'Complaint not found in tenant'},
    409: {'model': Envelope, 'description': 'Invalid package/school reference or manifest'},
    500: {'model': Envelope, 'description': 'Unexpected server error'},
    503: {'model': Envelope, 'description': 'Authentication/database unavailable'},
})


async def service_dependency(db: DatabaseDep,
    account: Annotated[AuthenticatedAccount, Depends(current_account, scope='function')]):
    try:
        yield ComplaintService(db, ActorScope(account.tenant_id, account.user_id))
    except PermissionDeniedError:
        raise HTTPException(403, 'Required Complaint permission is not granted') from None
    except RecordNotFoundError:
        raise HTTPException(404, 'Complaint not found') from None
    except ComplaintConflictError as exc:
        raise HTTPException(409, str(exc)) from None
    except IntegrityError as exc:
        if getattr(exc.orig, 'sqlstate', None) == '23503':
            raise HTTPException(409, 'Complaint reference unavailable') from None
        raise


ServiceDep = Annotated[ComplaintService, Depends(service_dependency, scope='function')]
Offset = Annotated[int, Query(ge=0, le=2147483647)]
Limit = Annotated[int, Query(ge=1, le=100)]


@router.post('', status_code=201, response_model=ComplaintEnvelope,
    description='Complaint.Write. Record immutable complaint for a package and active school in the same tenant; matching noncancelled delivery manifest required. Server reported_at, traceability edge/movement and stored event are atomic.')
async def create_complaint(request: Request, payload: ComplaintInput, service: ServiceDep):
    return envelope(request, code=201, data=await service.create(payload))


@router.get('', response_model=ComplaintPageEnvelope,
    description='Complaint.Read. No body; tenant complaints, optional package_id/school_id filters, created_at/ID descending, offset pagination.')
async def list_complaints(request: Request, service: ServiceDep, offset: Offset = 0, limit: Limit = 20,
    package_id: UUID | None = None, school_id: UUID | None = None):
    return envelope(request, data=await service.list(
        offset=offset, limit=limit, package_id=package_id, school_id=school_id,
    ))


@router.get('/reports', response_model=ComplaintReportPageEnvelope,
    description='Complaint.Read. Incident dashboard report list with package, production batch, current location, receiving/holding/material/traceability snapshots.')
async def list_complaint_reports(request: Request, service: ServiceDep, offset: Offset = 0, limit: Limit = 20,
    package_id: UUID | None = None, school_id: UUID | None = None):
    return envelope(request, data=await service.reports(
        offset=offset, limit=limit, package_id=package_id, school_id=school_id,
    ))


@router.get('/{identifier}', response_model=ComplaintEnvelope,
    description='Complaint.Read. UUID path, no body/query. Immutable evidence; missing/foreign/deleted record returns 404.')
async def get_complaint(request: Request, identifier: UUID, service: ServiceDep):
    return envelope(request, data=await service.get(identifier))


@router.get('/{identifier}/report', response_model=ComplaintReportEnvelope,
    description='Complaint.Read. Incident report for one complaint with package, production batch, location, receipt, consumption, raw materials and traceability movement snapshots.')
async def get_complaint_report(request: Request, identifier: UUID, service: ServiceDep):
    return envelope(request, data=await service.report(identifier))
