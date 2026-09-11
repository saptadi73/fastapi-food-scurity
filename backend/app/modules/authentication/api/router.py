import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config.settings import get_settings
from app.core.database.session import get_engine
from app.core.responses.envelope import Envelope, envelope
from app.modules.authentication.application.account_service import (
    AuthenticatedAccount,
    InvalidCredentialsError,
)
from app.modules.authentication.application.session_service import SessionService
from app.modules.authentication.infrastructure.access_tokens import (
    AccessTokenCodec,
    InvalidAccessTokenError,
)
from app.modules.authentication.schemas.http import (
    IdentityEnvelope,
    LoginPayload,
    LogoutEnvelope,
    RefreshPayload,
    TokensEnvelope,
)

logger = logging.getLogger('fsos')
router = APIRouter(prefix='/auth', tags=['Authentication'], responses={
    400: {'model': Envelope, 'description': 'Invalid JSON or request fields'},
    401: {'model': Envelope, 'description': 'Invalid credentials or session'},
    429: {'model': Envelope, 'description': 'Per-process authentication rate limit; Retry-After in seconds'},
    503: {'model': Envelope, 'description': 'Authentication configuration/database unavailable'},
    500: {'model': Envelope, 'description': 'Unexpected server error'},
})
bearer = HTTPBearer(auto_error=False, scheme_name='AccessToken')


def codec_dependency():
    settings = get_settings()
    try:
        if settings.jwt_access_token_minutes != 15 or settings.jwt_refresh_token_days != 7:
            raise ValueError('Unsupported token lifetime configuration')
        return AccessTokenCodec(settings.jwt_secret)
    except ValueError:
        raise HTTPException(503, 'Authentication unavailable') from None


async def database_dependency():
    try:
        factory = async_sessionmaker(get_engine(), expire_on_commit=False)
        async with factory() as db:
            yield db
    except (SQLAlchemyError, OSError, RuntimeError, ValueError):
        raise HTTPException(503, 'Authentication unavailable') from None


CodecDep = Annotated[AccessTokenCodec, Depends(codec_dependency)]
DatabaseDep = Annotated[AsyncSession, Depends(database_dependency, scope='function')]
BearerDep = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


def denied():
    return HTTPException(401, 'Invalid credentials or session', headers={'WWW-Authenticate': 'Bearer'})


def audit(request, action, outcome):
    logger.info('Authentication operation', extra={
        'request_id': request.state.request_id, 'auth_action': action, 'auth_outcome': outcome,
    })


def tokens_response(request, pair):
    return envelope(request, data={
        'access_token': pair.access_token.get_secret_value(),
        'refresh_token': pair.refresh_token.get_secret_value(),
        'refresh_expires_at': pair.refresh_expires_at,
        'token_type': pair.token_type, 'expires_in': pair.expires_in,
    })


@router.post('/login', response_model=TokensEnvelope, summary='Login pada tenant',
             description='JSON tenant_id, username, password. Public; verifies active account/tenant. Commits session before returning tokens. No cookies.')
async def login(request: Request, payload: LoginPayload, codec: CodecDep,
                db: DatabaseDep):
    try:
        async with db.begin():
            pair = await SessionService(db, codec).login(payload.tenant_id, payload.username, payload.password.get_secret_value())
    except InvalidCredentialsError:
        audit(request, 'login', 'denied')
        raise denied() from None
    audit(request, 'login', 'success')
    return tokens_response(request, pair)


@router.post('/refresh', response_model=TokensEnvelope, summary='Rotasi refresh token',
             description='JSON refresh_token is proof of possession. Reuse revokes its entire session and commits before returning generic 401. Serialize refresh requests.')
async def refresh(request: Request, payload: RefreshPayload, codec: CodecDep,
                  db: DatabaseDep):
    async with db.begin():
        result = await SessionService(db, codec).refresh(payload.refresh_token.get_secret_value())
    audit(request, 'refresh', 'success' if result.status == 'ROTATED' else 'denied')
    if result.status != 'ROTATED':
        raise denied()
    return tokens_response(request, result.tokens)


@router.post('/logout', response_model=LogoutEnvelope, summary='Cabut sesi refresh',
             description='JSON refresh_token. Revokes one family. Returns logged_out=true even for unknown/already revoked tokens. No bearer token required.')
async def logout(request: Request, payload: RefreshPayload, codec: CodecDep,
                 db: DatabaseDep):
    async with db.begin():
        await SessionService(db, codec).logout(payload.refresh_token.get_secret_value())
    audit(request, 'logout', 'completed')
    return envelope(request, data={'logged_out': True})


async def current_account(request: Request,
                          credentials: BearerDep,
                          codec: CodecDep,
                          db: DatabaseDep):
    if credentials is None:
        raise denied()
    try:
        async with db.begin():
            service = SessionService(db, codec)
            scope = await service.resolve_access(credentials.credentials)
            account = await service.accounts.snapshot(scope.tenant_id, scope.actor_id)
            yield account
    except (InvalidCredentialsError, InvalidAccessTokenError):
        audit(request, 'access', 'denied')
        raise denied() from None


@router.get('/me', response_model=IdentityEnvelope, summary='Identitas dan RBAC aktif',
            description='Requires Bearer access JWT with active sid, account and tenant. Returns current database roles/permissions; no business permission required.')
async def me(request: Request, account: Annotated[AuthenticatedAccount, Depends(current_account, scope='function')]):
    return envelope(request, data={
        'user_id': account.user_id, 'tenant_id': account.tenant_id,
        'roles': list(account.roles), 'permissions': list(account.permissions),
    })
