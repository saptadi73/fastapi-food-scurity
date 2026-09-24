from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from app.core.database.scope import ActorScope
from app.core.responses.envelope import Envelope, envelope
from app.modules.authentication.api.router import DatabaseDep, current_account
from app.modules.authentication.application.account_service import AuthenticatedAccount
from app.modules.authentication.infrastructure.authorization import PermissionDeniedError
from app.modules.signature.schemas import SignatureEnvelope, SignatureVerificationEnvelope
from app.modules.signature.service import SignatureConflictError, SignatureNotFoundError, SignatureService

router = APIRouter(prefix='/signatures', tags=['Digital Signature'], responses={
    400: {'model': Envelope}, 401: {'model': Envelope}, 403: {'model': Envelope},
    404: {'model': Envelope}, 409: {'model': Envelope}, 413: {'model': Envelope},
})


async def service_dependency(db: DatabaseDep,
    account: Annotated[AuthenticatedAccount, Depends(current_account, scope='function')]):
    try:
        yield SignatureService(db, ActorScope(account.tenant_id, account.user_id))
    except PermissionDeniedError:
        raise HTTPException(403, 'Required signature permission is not granted') from None
    except SignatureNotFoundError as exc:
        raise HTTPException(404, str(exc)) from None
    except SignatureConflictError as exc:
        raise HTTPException(409, str(exc)) from None


ServiceDep = Annotated[SignatureService, Depends(service_dependency, scope='function')]


@router.post('/targets/{entity_type}/{entity_id}', status_code=201, response_model=SignatureEnvelope,
             description='SchoolReceiving.Sign or Complaint.Sign. Multipart PNG/WebP signature, purpose and server-side signer snapshot; signer requires active assignment to target school.')
async def capture_signature(request: Request, entity_type: str, entity_id: UUID, service: ServiceDep,
                            purpose: Annotated[str, Form(min_length=1, max_length=100)],
                            file: UploadFile = File(...)):
    content_type = (file.content_type or '').lower()
    content = await file.read(2 * 1024 * 1024 + 1)
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(413, 'Signature image maximum size is 2 MiB')
    return envelope(request, code=201, data=await service.capture(
        entity_type.upper(), entity_id, purpose, content_type, content))


@router.get('/targets/{entity_type}/{entity_id}', response_model=SignatureEnvelope,
            description='Signature.Verify. Returns latest immutable signature metadata for target; image bytes are separate.')
async def get_signature(request: Request, entity_type: str, entity_id: UUID, service: ServiceDep):
    return envelope(request, data=await service.get_target(entity_type.upper(), entity_id))


@router.post('/evidence/{signature_id}/verify', response_model=SignatureVerificationEnvelope,
             description='Signature.Verify. Recalculates SHA-256 from stored bytes and returns VERIFIED, MISMATCH or MISSING.')
async def verify_signature(request: Request, signature_id: UUID, service: ServiceDep):
    return envelope(request, data=await service.verify(signature_id))


@router.get('/evidence/{signature_id}/image', response_class=FileResponse,
            description='Signature.Verify. Authorized image preview reconstructed from tenant and file UUID.')
async def signature_image(signature_id: UUID, service: ServiceDep):
    evidence = await service.get_by_id(signature_id)
    path = service.image_path(evidence)
    if not path.is_file():
        raise HTTPException(404, 'Signature image not found')
    return FileResponse(path, media_type=evidence['content_type'])
