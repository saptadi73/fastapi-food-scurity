from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.exc import IntegrityError

from app.core.database.scope import ActorScope, RecordNotFoundError, VersionConflictError
from app.core.responses.envelope import Envelope, envelope
from app.modules.authentication.api.router import DatabaseDep, current_account
from app.modules.authentication.application.account_service import AuthenticatedAccount
from app.modules.authentication.infrastructure.authorization import PermissionDeniedError
from app.modules.receiving.application.service import ReceivingConflictError
from app.modules.receiving.application.stock_service import StockService
from app.modules.receiving.schemas.receiving import (
    BatchEnvelope,
    BatchPageEnvelope,
    CancelInput,
    CompleteInput,
    ReceivingEnvelope,
    ReceivingInput,
    ReceivingPageEnvelope,
)
from app.modules.receiving.schemas.stock import (
    ManualStockIssueEnvelope,
    ManualStockIssueInput,
    ManualStockIssuePageEnvelope,
    PutawayInput,
    StockBalanceEnvelope,
    StockEntryEnvelope,
    StockIssuePageEnvelope,
    StockPageEnvelope,
)

router = APIRouter(tags=['Receiving'], responses={
    400: {'model': Envelope, 'description': 'Invalid payload, path or query'},
    401: {'model': Envelope, 'description': 'Invalid bearer session'},
    403: {'model': Envelope, 'description': 'Required permission is not granted'},
    404: {'model': Envelope, 'description': 'Receiving or batch not found in tenant'},
    409: {'model': Envelope, 'description': 'Stale version, duplicate batch/QR, invalid parent or transition'},
    500: {'model': Envelope, 'description': 'Unexpected server error'},
    503: {'model': Envelope, 'description': 'Authentication/database unavailable'},
})


async def service_dependency(db: DatabaseDep,
    account: Annotated[AuthenticatedAccount, Depends(current_account, scope='function')]):
    try:
        yield StockService(db, ActorScope(account.tenant_id, account.user_id))
    except PermissionDeniedError:
        raise HTTPException(403, 'Required permission is not granted') from None
    except RecordNotFoundError:
        raise HTTPException(404, 'Receiving or batch not found') from None
    except VersionConflictError:
        raise HTTPException(409, 'Receiving changed; reload before retrying') from None
    except ReceivingConflictError as exc:
        raise HTTPException(409, str(exc)) from None
    except IntegrityError as exc:
        if getattr(exc.orig, 'sqlstate', None) == '23505':
            raise HTTPException(409, 'Batch code or QR already exists in this tenant') from None
        if getattr(exc.orig, 'sqlstate', None) == '23503':
            raise HTTPException(409, 'Receiving reference unavailable') from None
        raise


ServiceDep = Annotated[StockService, Depends(service_dependency, scope='function')]
Offset = Annotated[int, Query(ge=0, le=2147483647)]
Limit = Annotated[int, Query(ge=1, le=100)]
Search = Annotated[str | None, Query(min_length=1, max_length=200)]
MaterialCategory = Annotated[str | None, Query(min_length=1, max_length=100)]


@router.post('/receivings', status_code=201, response_model=ReceivingEnvelope,
    description='Receiving.Write. Atomic header + 1..100 items/batches, registry and stored receiving.created event. Active tenant parents and supplier-material link required. UOM/tenant/operator are server-derived. Stock allocation follows separately through batch putaway.')
async def create_receiving(request: Request, payload: ReceivingInput, service: ServiceDep):
    return envelope(request, code=201, data=await service.create(payload))


@router.get('/receivings', response_model=ReceivingPageEnvelope,
    description='Receiving.Read. No body. Nondeleted tenant headers (no nested items), created_at/ID descending; optional AND filters, offset/limit and nullable next_offset.')
async def list_receivings(request: Request, service: ServiceDep, offset: Offset = 0, limit: Limit = 20,
    supplier_id: UUID | None = None, kitchen_id: UUID | None = None,
    status: Literal['CREATED', 'COMPLETED', 'CANCELLED'] | None = None):
    return envelope(request, data=await service.list(offset=offset, limit=limit,
        supplier_id=supplier_id, kitchen_id=kitchen_id, status=status))


@router.get('/receivings/{identifier}', response_model=ReceivingEnvelope,
    description='Receiving.Read. UUID path; no body/query. Tenant header with all items and nested batches, items sorted by UUID ascending; missing/foreign/deleted returns 404.')
async def get_receiving(request: Request, identifier: UUID, service: ServiceDep):
    return envelope(request, data=await service.get(identifier))


@router.post('/receivings/{identifier}/complete', response_model=ReceivingEnvelope,
    description='Receiving.Complete. CREATED only, expected_version and exactly one boolean decision per item required. Expired before current UTC date cannot be accepted. COMPLETED plus ACCEPTED/REJECTED batches; accepted batches add SUPPLIED/RECEIVED edges and RECEIVING movement to kitchen. Atomic registry and stored event. Retry after success returns 409; reload first.')
async def complete_receiving(request: Request, identifier: UUID, payload: CompleteInput, service: ServiceDep):
    return envelope(request, data=await service.finalize(identifier, payload))


@router.post('/receivings/{identifier}/cancel', response_model=ReceivingEnvelope,
    description='Receiving.Cancel. CREATED only, expected_version required. Header/batches become CANCELLED; item.accepted stays null. Atomic registry and stored event; no movement. No deletion or reversal of completed receipts. Retry after success returns 409.')
async def cancel_receiving(request: Request, identifier: UUID, payload: CancelInput, service: ServiceDep):
    return envelope(request, data=await service.finalize(identifier, payload, cancel=True))


@router.get('/raw-material-batches', response_model=BatchPageEnvelope,
    description='RawMaterialBatch.Read. No body; nondeleted tenant batches; optional AND filters, search by material code/name or batch code, material_category and sort CREATED_DESC/FIFO/FEFO. Status is a receiving decision, not an available-stock balance.')
async def list_batches(request: Request, service: ServiceDep, offset: Offset = 0, limit: Limit = 20,
    receiving_id: UUID | None = None, raw_material_id: UUID | None = None, supplier_id: UUID | None = None,
    status: Literal['CREATED', 'ACCEPTED', 'REJECTED', 'CANCELLED'] | None = None,
    search: Search = None, material_category: MaterialCategory = None,
    sort: Literal['CREATED_DESC', 'FIFO', 'FEFO'] = 'CREATED_DESC'):
    return envelope(request, data=await service.list(batch=True, offset=offset, limit=limit,
        receiving_id=receiving_id, raw_material_id=raw_material_id, supplier_id=supplier_id, status=status,
        search=search, material_category=material_category, sort=sort))


@router.get('/raw-material-batches/resolve', response_model=BatchEnvelope,
    description='RawMaterialBatch.Read. Resolve persisted QR batch pada tenant sesi menjadi RawMaterialBatchData; surrounding whitespace is ignored. Query qr_code wajib; missing/foreign/deleted returns 404.')
async def resolve_batch_qr(request: Request, qr_code: Annotated[str, Query(min_length=1, max_length=255)], service: ServiceDep):
    return envelope(request, data=await service.resolve_batch_qr(qr_code.strip()))


@router.get('/raw-material-batches/{identifier}', response_model=BatchEnvelope,
    description='RawMaterialBatch.Read. UUID path; no body/query. Missing/foreign/deleted returns 404. Batches are created/finalized only through receiving; no direct edit/delete endpoint.')
async def get_batch(request: Request, identifier: UUID, service: ServiceDep):
    return envelope(request, data=await service.get(identifier, batch=True))


@router.post('/raw-material-batches/{identifier}/putaway', status_code=201, response_model=StockEntryEnvelope,
    description='Stock.Putaway. UUID batch; expected_version, storage_id, optional zone_id and positive decimal quantity. Partial allocation of accepted unallocated stock to active storage/zone in receiving kitchen, matching material storage type. Expiry uses UTC date. Atomic ledger, batch version, registry, STORAGE movement and stock.putaway event. Retry with old version returns 409.')
async def putaway(request: Request, identifier: UUID, payload: PutawayInput, service: ServiceDep):
    return envelope(request, code=201, data=await service.putaway(identifier, payload))


@router.post('/raw-material-batches/{identifier}/manual-stock-issues', status_code=201,
    response_model=ManualStockIssueEnvelope,
    description='Stock.Issue. UUID batch; expected_version, storage_id, optional zone_id, positive quantity, optional issued_at, reason and reference_code. Records scanned/manual issue from storage without production batch, updates batch version, movement ISSUE and stock.manual_issued event.')
async def manual_stock_issue(request: Request, identifier: UUID, payload: ManualStockIssueInput, service: ServiceDep):
    return envelope(request, code=201, data=await service.manual_issue(identifier, payload))


@router.get('/raw-material-batches/{identifier}/stock', response_model=StockBalanceEnvelope,
    description='Stock.Read. UUID batch; no body/query. Accepted, allocated, unallocated and available quantities in receiving UOM, with storage balances and current batch version. Availability excludes expired batches, inactive parents/storage and incompatible storage types. Available balance subtracts production issues; unallocated balance subtracts historical putaway, not issues. No reservation.')
async def stock_balance(request: Request, identifier: UUID, service: ServiceDep):
    return envelope(request, data=await service.balance(identifier))


@router.get('/raw-material-batches/{identifier}/stock-entries', response_model=StockPageEnvelope,
    description='Stock.Read. UUID batch; no body; offset>=0 (max 2147483647), limit 1..100 default 20. Immutable putaway ledger, batch_version descending, nullable next_offset. Missing/foreign batch returns 404.')
async def stock_ledger(request: Request, identifier: UUID, service: ServiceDep, offset: Offset = 0, limit: Limit = 20):
    return envelope(request, data=await service.ledger(identifier, offset=offset, limit=limit))


@router.get('/raw-material-batches/{identifier}/stock-issues', response_model=StockIssuePageEnvelope,
    description='Stock.Read. UUID batch; no body; offset/limit pagination. Immutable production issues backed by storage, batch_version descending; legacy items without storage excluded. Missing/foreign/deleted batch 404.')
async def stock_issues(request: Request, identifier: UUID, service: ServiceDep, offset: Offset = 0, limit: Limit = 20):
    return envelope(request, data=await service.issues(identifier, offset=offset, limit=limit))


@router.get('/raw-material-batches/{identifier}/manual-stock-issues', response_model=ManualStockIssuePageEnvelope,
    description='Stock.Read. UUID batch; no body; offset/limit pagination. Immutable manual/scanned stock issues, batch_version descending. Missing/foreign/deleted batch 404.')
async def manual_stock_issues(request: Request, identifier: UUID, service: ServiceDep, offset: Offset = 0, limit: Limit = 20):
    return envelope(request, data=await service.manual_issues(identifier, offset=offset, limit=limit))
