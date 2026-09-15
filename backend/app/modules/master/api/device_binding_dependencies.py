from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy.exc import IntegrityError

from app.core.database.scope import ActorScope, RecordNotFoundError, VersionConflictError
from app.modules.authentication.api.router import DatabaseDep, current_account
from app.modules.authentication.application.account_service import AuthenticatedAccount
from app.modules.authentication.infrastructure.authorization import PermissionDeniedError
from app.modules.master.application.device_binding_service import DeviceBindingConflictError, DeviceBindingService


def device_binding_dependency():
    async def dependency(db: DatabaseDep,
                         account: Annotated[AuthenticatedAccount, Depends(current_account, scope='function')]):
        try:
            yield DeviceBindingService(db, ActorScope(account.tenant_id, account.user_id))
        except PermissionDeniedError:
            raise HTTPException(403, 'Required Device permission is not granted') from None
        except RecordNotFoundError:
            raise HTTPException(404, 'Device binding not found') from None
        except VersionConflictError:
            raise HTTPException(409, 'Device binding changed; reload before retrying') from None
        except DeviceBindingConflictError as exc:
            raise HTTPException(409, str(exc)) from None
        except IntegrityError as exc:
            if getattr(exc.orig, 'sqlstate', None) == '23505':
                raise HTTPException(409, 'Device already bound to this vehicle in this tenant') from None
            if getattr(exc.orig, 'sqlstate', None) == '23503':
                raise HTTPException(409, 'Active device and vehicle required') from None
            raise
        except ValueError:
            raise HTTPException(400, 'Invalid device binding input') from None
    return dependency
