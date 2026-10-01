from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.database.session import get_admin_engine
from app.core.responses.envelope import Envelope, envelope
from app.modules.authentication.api.router import current_account
from app.modules.authentication.application.account_service import AuthenticatedAccount
from app.modules.demo.cleanup import DEFAULT_TENANT_CODE, cleanup
from app.modules.master.infrastructure.orm import Tenant

router = APIRouter(prefix='/demo', tags=['Demo'], responses={
    401: {'model': Envelope, 'description': 'Invalid bearer session'},
    403: {'model': Envelope, 'description': 'Only ADMIN on FSOS_EXPO may reset the demo'},
    503: {'model': Envelope, 'description': 'Authentication/database unavailable'},
})


@router.post('/reset', response_model=Envelope,
             description='Requires an active bearer session with role ADMIN on tenant FSOS_EXPO. Hard-deletes only transactional demo rows using ADMIN_DATABASE_URL; master data, users and tenant are preserved. No event is emitted.')
async def reset(request: Request,
                account: Annotated[AuthenticatedAccount, Depends(current_account, scope='function')]):
    if 'ADMIN' not in account.roles:
        raise HTTPException(403, 'Demo reset requires the ADMIN role on FSOS_EXPO')

    factory = async_sessionmaker(get_admin_engine(), expire_on_commit=False)
    async with factory() as session, session.begin():
        result = await session.execute(select(Tenant.tenant_id, Tenant.tenant_code).where(
            Tenant.tenant_id == account.tenant_id,
            Tenant.tenant_code == DEFAULT_TENANT_CODE,
            Tenant.deleted_at.is_(None),
        ))
        row = result.one_or_none()
        if row is None:
            raise HTTPException(403, 'Demo reset is only available for tenant FSOS_EXPO')
        removed = await cleanup(session, row.tenant_id)
    return envelope(request, message='Demo transactional data reset', data={
        'tenant_code': row.tenant_code, 'tenant_id': row.tenant_id, 'removed': removed,
    })
