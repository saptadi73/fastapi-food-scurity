import asyncio
import logging
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pythonjsonlogger.json import JsonFormatter
from sqlalchemy.ext.asyncio import async_sessionmaker
from starlette.exceptions import HTTPException

from app.core.config.settings import get_settings
from app.core.database.readiness import check_readiness
from app.core.database.session import close_database, get_engine
from app.core.responses.envelope import Envelope, envelope
from app.modules.authentication.api.rate_limit import AuthLimitMiddleware, AuthRateLimiter
from app.modules.authentication.api.router import router as auth_router
from app.modules.authentication.api.users import router as users_router
from app.modules.complaint.api import router as complaints_router
from app.modules.consumption.api.workflow import router as school_workflow_router
from app.modules.dashboard.api import router as dashboard_router
from app.modules.fleet.api.deliveries import router as deliveries_router
from app.modules.master.api.alarm_rules import router as alarm_router
from app.modules.master.api.device_bindings import router as device_bindings_router
from app.modules.master.api.devices import router as devices_router
from app.modules.master.api.drivers import router as drivers_router
from app.modules.master.api.food_items import router as food_items_router
from app.modules.master.api.holding_rules import router as holding_router
from app.modules.master.api.kitchens import router as kitchens_router
from app.modules.master.api.packaging_types import router as packaging_types_router
from app.modules.master.api.raw_materials import router as raw_materials_router
from app.modules.master.api.recipes import router as recipes_router
from app.modules.master.api.schools import router as schools_router
from app.modules.master.api.storage_zones import router as storage_zones_router
from app.modules.master.api.storages import router as storages_router
from app.modules.master.api.supplier_materials import router as supplier_materials_router
from app.modules.master.api.suppliers import router as suppliers_router
from app.modules.master.api.vehicles import router as vehicles_router
from app.modules.notification.api import router as notifications_router
from app.modules.packaging.api.router import router as packages_router
from app.modules.production.api.router import router as production_router
from app.modules.recall.api import router as recalls_router
from app.modules.signature.api import router as signatures_router
from app.modules.receiving.api.router import router as receiving_router
from app.modules.telemetry.api.alarms import router as telemetry_alarm_router
from app.modules.telemetry.api.ingestion import router as telemetry_ingestion_router
from app.modules.telemetry.api.food_measurements import router as food_measurements_router
from app.modules.telemetry.api.mqtt_events import router as mqtt_events_router
from app.modules.telemetry.api.sessions import router as device_session_router
from app.modules.telemetry.application.mqtt_consumer import MQTTConsumer
from app.modules.traceability.api import router as traceability_router
from app.modules.uploads.api import router as uploads_router

logger = logging.getLogger("fsos")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(get_settings().log_level)
    consumer = None
    consumer_task = None
    settings = get_settings()
    if settings.mqtt_consumer_enabled:
        if settings.mqtt_tenant_id is None:
            raise RuntimeError('MQTT_TENANT_ID wajib diisi ketika MQTT_CONSUMER_ENABLED=true')
        consumer = MQTTConsumer(settings, async_sessionmaker(get_engine(), expire_on_commit=False))
        consumer_task = asyncio.create_task(consumer.run(), name='fsos-mqtt-consumer')
    try:
        yield
    finally:
        if consumer is not None:
            await consumer.stop()
        if consumer_task is not None:
            consumer_task.cancel()
            await asyncio.gather(consumer_task, return_exceptions=True)
        await close_database()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Backend FSOS dengan endpoint sistem dan autentikasi sesi. API holding dan alarm rule tersedia; modul bisnis lain bertahap.",
        lifespan=lifespan,
    )
    app.state.auth_limiter = AuthRateLimiter()
    app.include_router(auth_router, prefix=settings.api_prefix)
    app.include_router(users_router, prefix=settings.api_prefix)
    app.include_router(holding_router, prefix=settings.api_prefix)
    app.include_router(alarm_router, prefix=settings.api_prefix)
    app.include_router(telemetry_alarm_router, prefix=settings.api_prefix)
    app.include_router(telemetry_ingestion_router, prefix=settings.api_prefix)
    app.include_router(food_measurements_router, prefix=settings.api_prefix)
    app.include_router(mqtt_events_router, prefix=settings.api_prefix)
    app.include_router(device_session_router, prefix=settings.api_prefix)
    app.include_router(kitchens_router, prefix=settings.api_prefix)
    app.include_router(storages_router, prefix=settings.api_prefix)
    app.include_router(storage_zones_router, prefix=settings.api_prefix)
    app.include_router(suppliers_router, prefix=settings.api_prefix)
    app.include_router(raw_materials_router, prefix=settings.api_prefix)
    app.include_router(supplier_materials_router, prefix=settings.api_prefix)
    app.include_router(schools_router, prefix=settings.api_prefix)
    app.include_router(drivers_router, prefix=settings.api_prefix)
    app.include_router(devices_router, prefix=settings.api_prefix)
    app.include_router(device_bindings_router, prefix=settings.api_prefix)
    app.include_router(dashboard_router, prefix=settings.api_prefix)
    app.include_router(vehicles_router, prefix=settings.api_prefix)
    app.include_router(food_items_router, prefix=settings.api_prefix)
    app.include_router(recipes_router, prefix=settings.api_prefix)
    app.include_router(packaging_types_router, prefix=settings.api_prefix)
    app.include_router(school_workflow_router, prefix=settings.api_prefix)
    app.include_router(deliveries_router, prefix=settings.api_prefix)
    app.include_router(complaints_router, prefix=settings.api_prefix)
    app.include_router(recalls_router, prefix=settings.api_prefix)
    app.include_router(signatures_router, prefix=settings.api_prefix)
    app.include_router(notifications_router, prefix=settings.api_prefix)
    app.include_router(traceability_router, prefix=settings.api_prefix)
    app.include_router(packages_router, prefix=settings.api_prefix)
    app.include_router(production_router, prefix=settings.api_prefix)
    app.include_router(receiving_router, prefix=settings.api_prefix)
    app.include_router(uploads_router, prefix=settings.api_prefix)
    original_openapi = app.openapi

    master_like_paths = (
        f'{settings.api_prefix}/auth/',
        f'{settings.api_prefix}/holding-rules',
        f'{settings.api_prefix}/alarm-rules',
        f'{settings.api_prefix}/alarms',
        f'{settings.api_prefix}/telemetry',
        f'{settings.api_prefix}/mqtt',
        f'{settings.api_prefix}/device-sessions',
        f'{settings.api_prefix}/kitchens',
        f'{settings.api_prefix}/storages',
        f'{settings.api_prefix}/storage-zones',
        f'{settings.api_prefix}/suppliers',
        f'{settings.api_prefix}/raw-materials',
        f'{settings.api_prefix}/supplier-materials',
        f'{settings.api_prefix}/schools',
        f'{settings.api_prefix}/drivers',
        f'{settings.api_prefix}/devices',
        f'{settings.api_prefix}/device-bindings',
        f'{settings.api_prefix}/dashboard',
        f'{settings.api_prefix}/vehicles',
        f'{settings.api_prefix}/receivings',
        f'{settings.api_prefix}/raw-material-batches',
        f'{settings.api_prefix}/food-items',
        f'{settings.api_prefix}/recipes',
        f'{settings.api_prefix}/production-batches',
        f'{settings.api_prefix}/packages',
        f'{settings.api_prefix}/packaging-types',
        f'{settings.api_prefix}/deliveries',
        f'{settings.api_prefix}/complaints',
        f'{settings.api_prefix}/recalls',
        f'{settings.api_prefix}/notifications',
        f'{settings.api_prefix}/traceability',
        f'{settings.api_prefix}/school-receivings',
        f'{settings.api_prefix}/consumptions',
        f'{settings.api_prefix}/uploads',
    )

    def documented_openapi():
        schema = original_openapi()
        for path, operations in schema['paths'].items():
            if path.startswith(master_like_paths):
                for operation in operations.values():
                    operation.get('responses', {}).pop('422', None)
        return schema

    app.openapi = documented_openapi
    app.add_middleware(AuthLimitMiddleware, prefix=f'{settings.api_prefix}/auth/')
    if settings.environment in {"development", "testing"}:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Correlation-ID"],
            expose_headers=["X-Request-ID", "Retry-After"],
        )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request.state.request_id = str(uuid4())
        request.state.correlation_id = request.headers.get(
            "X-Correlation-ID", request.state.request_id
        )[:128]
        request.state.started_at = perf_counter()
        is_auth = request.url.path.startswith(f'{settings.api_prefix}/auth/')
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("Unhandled request error")
            response = JSONResponse(
                envelope(request, code=500, message="Internal Server Error").model_dump(
                    mode="json"
                ),
                status_code=500,
            )
        response.headers["X-Request-ID"] = request.state.request_id
        if is_auth or request.url.path.startswith(master_like_paths):
            response.headers['Cache-Control'] = 'no-store'
            response.headers['Pragma'] = 'no-cache'
        logger.info(
            "HTTP request",
            extra={
                "request_id": request.state.request_id,
                "method": request.method,
                "status_code": response.status_code,
            },
        )
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return JSONResponse(
            envelope(request, code=exc.status_code, message=str(exc.detail)).model_dump(
                mode="json"
            ),
            status_code=exc.status_code,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        errors = [
            {"field": ".".join(map(str, error["loc"])), "message": error["msg"]}
            for error in exc.errors()
        ]
        return JSONResponse(
            envelope(
                request, code=400, message="Validation Error", errors=errors
            ).model_dump(mode="json"),
            status_code=400,
        )

    @app.get(
        f"{settings.api_prefix}/health",
        response_model=Envelope,
        tags=["System"],
        summary="Periksa proses API",
        description=(
            "Liveness untuk development/monitoring, tanpa payload atau parameter. "
            "Permission: publik, hanya status proses. Business rule: tidak memeriksa "
            "koneksi PostgreSQL, Redis, atau MQTT. Response 200: data.status=ok; "
            "error 500: kegagalan internal."
        ),
    )
    async def health(request: Request):
        return envelope(request, data={"status": "ok", "service": settings.app_name})

    @app.get(
        f"{settings.api_prefix}/ready",
        response_model=Envelope,
        responses={503: {"model": Envelope, "description": "Dependensi belum siap"}},
        tags=["System"],
        summary="Periksa kesiapan database",
        description=(
            "Permission: publik, tanpa payload atau parameter. Memeriksa PostgreSQL 18, "
            "PostGIS/pgcrypto, dan revisi database terhadap Alembic heads aplikasi. "
            "200: data.status=ready; 503: data.status=not_ready dengan status pemeriksaan. "
            "Timeout default 3 detik. Tidak menjalankan migrasi. Redis/MQTT belum menjadi "
            "dependensi runtime; kesiapan ini tidak menyatakan modul bisnis sudah lengkap."
        ),
    )
    async def ready(request: Request):
        checks = await check_readiness()
        is_ready = all(value == "ok" for value in checks.values())
        code = 200 if is_ready else 503
        return JSONResponse(
            envelope(request, code=code, message="Ready" if is_ready else "Not Ready",
                     data={"status": "ready" if is_ready else "not_ready", "checks": checks}
                     ).model_dump(mode="json"),
            status_code=code,
            headers={"Cache-Control": "no-store"},
        )

    @app.get(
        f"{settings.api_prefix}/health/database",
        response_model=Envelope,
        responses={503: {"model": Envelope, "description": "Koneksi database belum siap"}},
        tags=["System"],
        summary="Test koneksi database",
        description=(
            "Permission: publik, tanpa payload atau parameter. Endpoint eksplisit untuk "
            "frontend/devops menguji koneksi database aplikasi. Memakai pemeriksaan yang "
            "sama dengan /ready: PostgreSQL 18, PostGIS/pgcrypto, dan Alembic heads. "
            "200: data.status=ready; 503: data.status=not_ready. Tidak mengekspos URL, "
            "nama database, credential, exception SQL, atau menjalankan migrasi."
        ),
    )
    async def database_health(request: Request):
        checks = await check_readiness()
        is_ready = all(value == "ok" for value in checks.values())
        code = 200 if is_ready else 503
        return JSONResponse(
            envelope(request, code=code, message="Database Ready" if is_ready else "Database Not Ready",
                     data={"status": "ready" if is_ready else "not_ready", "checks": checks}
                     ).model_dump(mode="json"),
            status_code=code,
            headers={"Cache-Control": "no-store"},
        )

    return app


app = create_app()
