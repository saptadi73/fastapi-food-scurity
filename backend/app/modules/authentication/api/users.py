from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.database.scope import ActorScope
from app.core.responses.envelope import Envelope, envelope
from app.modules.authentication.api.router import DatabaseDep, current_account
from app.modules.authentication.application.account_service import AuthenticatedAccount
from app.modules.authentication.application.user_service import (
    UserAdministrationService, UserConflictError, UserNotFoundError,
)
from app.modules.authentication.infrastructure.authorization import PermissionDeniedError, require_permission
from app.modules.authentication.schemas.users import (
    RoleListEnvelope, UserCreate, UserEnvelope, UserPageEnvelope, UserUpdate,
)

router = APIRouter(prefix='/users', tags=['User Administration'], responses={
    400: {'model': Envelope}, 401: {'model': Envelope}, 403: {'model': Envelope},
    409: {'model': Envelope}, 503: {'model': Envelope}, 500: {'model': Envelope},
})
AccountDep = Annotated[AuthenticatedAccount, Depends(current_account, scope='function')]


async def authorize(db, account, *permissions):
    scope = ActorScope(account.tenant_id, account.user_id)
    try:
        for permission in permissions:
            await require_permission(db, scope, permission)
    except PermissionDeniedError:
        raise HTTPException(403, 'Required permission is not granted') from None
    return scope


@router.get('/roles', response_model=RoleListEnvelope,
            description='Bearer + User.Read. Lists nondeleted roles belonging to the current tenant.')
async def list_roles(request: Request, account: AccountDep, db: DatabaseDep):
    scope = await authorize(db, account, 'User.Read')
    data = await UserAdministrationService(db, scope).roles()
    return envelope(request, data=data)


@router.get('', response_model=UserPageEnvelope,
            description='Bearer + User.Read. Tenant-scoped users with roles and kitchen/school assignments.')
async def list_users(request: Request, account: AccountDep, db: DatabaseDep,
                     status: str | None = Query(default=None, pattern='^(ACTIVE|INACTIVE|LOCKED)$'),
                     offset: int = Query(default=0, ge=0), limit: int = Query(default=20, ge=1, le=100)):
    scope = await authorize(db, account, 'User.Read')
    data = await UserAdministrationService(db, scope).list(offset, limit, status)
    return envelope(request, data=data)


@router.get('/{identifier}', response_model=UserEnvelope,
            description='Bearer + User.Read. Returns one nondeleted user from the current tenant.')
async def get_user(identifier: str, request: Request, account: AccountDep, db: DatabaseDep):
    from uuid import UUID
    try:
        user_id = UUID(identifier)
        scope = await authorize(db, account, 'User.Read')
        data = await UserAdministrationService(db, scope).detail(user_id)
    except (ValueError, UserNotFoundError):
        raise HTTPException(404, 'User not found in tenant') from None
    return envelope(request, data=data)


@router.post('', response_model=UserEnvelope, status_code=201,
             description='Bearer + User.Write + Role.Assign. Registers an active tenant user atomically. Password is write-only.')
async def create_user(request: Request, payload: UserCreate, account: AccountDep, db: DatabaseDep):
    try:
        scope = await authorize(db, account, 'User.Write', 'Role.Assign')
        data = await UserAdministrationService(db, scope).create(payload)
    except UserConflictError as exc:
        raise HTTPException(409, str(exc)) from None
    return envelope(request, data=data)


@router.put('/{identifier}', response_model=UserEnvelope,
            description='Bearer + User.Write + Role.Assign. Replaces profile, status, roles and location assignments using expected_version.')
async def update_user(identifier: str, request: Request, payload: UserUpdate,
                      account: AccountDep, db: DatabaseDep):
    from uuid import UUID
    try:
        user_id = UUID(identifier)
        scope = await authorize(db, account, 'User.Write', 'Role.Assign')
        data = await UserAdministrationService(db, scope).update(user_id, payload)
    except (ValueError, UserNotFoundError):
        raise HTTPException(404, 'User not found in tenant') from None
    except UserConflictError as exc:
        raise HTTPException(409, str(exc)) from None
    return envelope(request, data=data)
