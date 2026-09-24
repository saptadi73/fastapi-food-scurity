from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.database.scope import ActorScope
from app.core.responses.envelope import Envelope, envelope
from app.modules.authentication.api.router import DatabaseDep, current_account
from app.modules.authentication.application.account_service import AuthenticatedAccount
from app.modules.authentication.infrastructure.authorization import PermissionDeniedError
from app.modules.telemetry.application.food_measurement_service import (
    FoodTemperatureMeasurementError, FoodTemperatureMeasurementService,
)
from app.modules.telemetry.schemas.food_measurement import (
    FoodTemperatureMeasurementEnvelope, FoodTemperatureMeasurementInput,
)

router = APIRouter(prefix='/food-temperature-measurements', tags=['Food temperature'], responses={
    400: {'model': Envelope}, 401: {'model': Envelope}, 403: {'model': Envelope},
    409: {'model': Envelope}, 503: {'model': Envelope},
})


async def service_dependency(db: DatabaseDep,
    account: Annotated[AuthenticatedAccount, Depends(current_account, scope='function')]):
    try:
        yield FoodTemperatureMeasurementService(db, ActorScope(account.tenant_id, account.user_id))
    except PermissionDeniedError:
        raise HTTPException(403, 'FoodTemperature.Read permission is not granted') from None
    except FoodTemperatureMeasurementError as exc:
        raise HTTPException(409, str(exc)) from None


ServiceDep = Annotated[FoodTemperatureMeasurementService, Depends(service_dependency, scope='function')]


@router.post('', response_model=FoodTemperatureMeasurementEnvelope,
             description='FoodTemperature.Read. Select latest fresh unbound Celsius sample from an active FOOD_TEMPERATURE device. Records contextual audit event; does not monitor storage or mutate the target transaction.')
async def latest_food_temperature(request: Request, payload: FoodTemperatureMeasurementInput,
                                  service: ServiceDep):
    return envelope(request, data=await service.latest(payload))
