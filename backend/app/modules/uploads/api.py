from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.config.settings import get_settings
from app.core.database.scope import ActorScope
from app.core.responses.envelope import Envelope, envelope
from app.modules.authentication.api.router import DatabaseDep, current_account
from app.modules.authentication.application.account_service import AuthenticatedAccount
from app.modules.authentication.infrastructure.authorization import require_permission
from app.modules.authentication.infrastructure.authorization import PermissionDeniedError

router = APIRouter(prefix='/uploads', tags=['Uploads'])
ALLOWED_TYPES = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp'}

class UploadData(BaseModel):
    file_id: UUID
    reference: str
    content_type: str
    size_bytes: int

class UploadEnvelope(Envelope):
    data: UploadData

async def account_scope(db: DatabaseDep,
    account: Annotated[AuthenticatedAccount, Depends(current_account, scope='function')]):
    return db, ActorScope(account.tenant_id, account.user_id)

ScopeDep = Annotated[tuple, Depends(account_scope, scope='function')]

@router.post('/receiving-photo', status_code=201, response_model=UploadEnvelope,
    description='Receiving.Write. Upload foto inspeksi bahan sebagai multipart file. JPEG, PNG, atau WebP; maksimal sesuai UPLOAD_MAX_BYTES (default 10 MiB). Reference hasil upload dapat dipakai sebagai items[].photo pada POST /receivings.')
async def upload_receiving_photo(request: Request, upload: ScopeDep,
                                 file: UploadFile = File(...)):
    db, scope = upload
    try:
        await require_permission(db, scope, 'Receiving.Write')
    except PermissionDeniedError:
        raise HTTPException(403, 'Required permission is not granted') from None
    content_type = (file.content_type or '').lower()
    extension = ALLOWED_TYPES.get(content_type)
    if extension is None:
        raise HTTPException(400, 'Foto harus berformat JPEG, PNG, atau WebP')
    settings = get_settings()
    content = await file.read(settings.upload_max_bytes + 1)
    if len(content) > settings.upload_max_bytes:
        raise HTTPException(413, f'Ukuran foto maksimal {settings.upload_max_bytes // (1024 * 1024)} MiB')
    if not content:
        raise HTTPException(400, 'File foto tidak boleh kosong')
    file_id = uuid4()
    tenant_dir = settings.upload_dir / str(scope.tenant_id)
    tenant_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f'{file_id}{extension}'
    (tenant_dir / stored_name).write_bytes(content)
    return envelope(request, code=201, data=UploadData(
        file_id=file_id, reference=f'receiving-photo/{scope.tenant_id}/{stored_name}',
        content_type=content_type, size_bytes=len(content),
    ))

@router.get('/receiving-photo/{file_id}', response_class=FileResponse,
    description='Receiving.Read. Mengambil foto inspeksi yang sebelumnya diunggah pada tenant sesi.')
async def get_receiving_photo(file_id: UUID, upload: ScopeDep):
    db, scope = upload
    try:
        await require_permission(db, scope, 'Receiving.Read')
    except PermissionDeniedError:
        raise HTTPException(403, 'Required permission is not granted') from None
    directory = get_settings().upload_dir / str(scope.tenant_id)
    matches = list(directory.glob(f'{file_id}.*')) if directory.is_dir() else []
    if not matches or matches[0].suffix.lower() not in ALLOWED_TYPES.values():
        raise HTTPException(404, 'Foto tidak ditemukan')
    media_type = next(kind for kind, suffix in ALLOWED_TYPES.items()
                      if suffix == matches[0].suffix.lower())
    return FileResponse(matches[0], media_type=media_type)
