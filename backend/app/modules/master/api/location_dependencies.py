from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy.exc import IntegrityError

from app.core.database.scope import ActorScope, RecordNotFoundError, VersionConflictError
from app.modules.authentication.api.router import DatabaseDep, current_account
from app.modules.authentication.application.account_service import AuthenticatedAccount
from app.modules.authentication.infrastructure.authorization import PermissionDeniedError
from app.modules.master.application.location_service import LocationConflictError, LocationService
from app.modules.master.application.master_deletion import MasterInUseError


def location_dependency(kind):
    async def dependency(db: DatabaseDep,
                         account: Annotated[AuthenticatedAccount, Depends(current_account, scope='function')]):
        try:
            yield LocationService(db, ActorScope(account.tenant_id, account.user_id), kind)
        except PermissionDeniedError:
            raise HTTPException(403, 'Required permission is not granted') from None
        except MasterInUseError:
            raise HTTPException(409, 'Master record is still referenced') from None
        except RecordNotFoundError:
            raise HTTPException(404, 'Location not found') from None
        except VersionConflictError:
            raise HTTPException(409, 'Location changed; reload before retrying') from None
        except LocationConflictError as exc:
            raise HTTPException(409, str(exc)) from None
        except IntegrityError as exc:
            if getattr(exc.orig, 'sqlstate', None) == '23505':
                raise HTTPException(409, 'Location code already exists in this scope') from None
            if getattr(exc.orig, 'sqlstate', None) == '23503':
                raise HTTPException(409, 'Parent location unavailable') from None
            raise
        except ValueError:
            raise HTTPException(400, 'Invalid location input') from None
    return dependency
