from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.database.scope import ActorScope, RecordNotFoundError
from app.core.responses.envelope import Envelope, envelope
from app.modules.authentication.api.router import DatabaseDep, current_account
from app.modules.authentication.application.account_service import AuthenticatedAccount
from app.modules.authentication.infrastructure.authorization import PermissionDeniedError
from app.modules.telemetry.application.ingestion_service import (
    TelemetryIngestionConflictError,
    TelemetryIngestionService,
)
from app.modules.telemetry.schemas.ingestion import (
    GpsIngestEnvelope,
    GpsIngestInput,
    TemperatureIngestEnvelope,
    TemperatureIngestInput,
)

router = APIRouter(prefix='/telemetry', tags=['Telemetry Ingestion'], responses={
    400: {'model': Envelope, 'description': 'Invalid telemetry payload'},
    401: {'model': Envelope, 'description': 'Missing/invalid bearer session'},
    403: {'model': Envelope, 'description': 'Required telemetry permission missing'},
    404: {'model': Envelope, 'description': 'Referenced device/vehicle/storage not found'},
    409: {'model': Envelope, 'description': 'Referenced master inactive or invalid'},
    500: {'model': Envelope, 'description': 'Unexpected server error'},
    503: {'model': Envelope, 'description': 'Authentication/database unavailable'},
})


async def telemetry_service(db: DatabaseDep,
                            account: Annotated[AuthenticatedAccount, Depends(current_account, scope='function')]):
    try:
        yield TelemetryIngestionService(db, ActorScope(account.tenant_id, account.user_id))
    except PermissionDeniedError:
        raise HTTPException(403, 'Required permission is not granted') from None
    except RecordNotFoundError:
        raise HTTPException(404, 'Telemetry reference not found') from None
    except TelemetryIngestionConflictError as exc:
        raise HTTPException(409, str(exc)) from None


ServiceDep = Annotated[TelemetryIngestionService, Depends(telemetry_service, scope='function')]


@router.post('/gps', status_code=201, response_model=GpsIngestEnvelope,
             description='Telemetry.Ingest. Append one GPS sample for a tenant vehicle. HTTP ingestion only; mqtt_message_id null. Used by delivery tracking latest GPS.')
async def ingest_gps(request: Request, payload: GpsIngestInput, service: ServiceDep):
    return envelope(request, code=201, data=await service.gps(payload))


@router.post('/temperatures', status_code=201, response_model=TemperatureIngestEnvelope,
             description='Telemetry.Ingest. Append one temperature sample for a tenant device/storage. HTTP ingestion only; mqtt_message_id null. Used by storage/fleet tracking latest temperature.')
async def ingest_temperature(request: Request, payload: TemperatureIngestInput, service: ServiceDep):
    return envelope(request, code=201, data=await service.temperature(payload))
