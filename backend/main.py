import logging
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pythonjsonlogger.json import JsonFormatter
from starlette.exceptions import HTTPException

from app.core.config.settings import get_settings
from app.core.database.readiness import check_readiness
from app.core.database.session import close_database
from app.core.responses.envelope import Envelope, envelope
from app.modules.authentication.api.rate_limit import AuthLimitMiddleware, AuthRateLimiter
from app.modules.authentication.api.router import router as auth_router

logger = logging.getLogger("fsos")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(get_settings().log_level)
    try:
        yield
    finally:
        await close_database()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Backend FSOS dengan endpoint sistem dan autentikasi sesi. API bisnis belum tersedia.",
        lifespan=lifespan,
    )
    app.state.auth_limiter = AuthRateLimiter()
    app.include_router(auth_router, prefix=settings.api_prefix)
    original_openapi = app.openapi

    def documented_openapi():
        schema = original_openapi()
        for path, operations in schema['paths'].items():
            if path.startswith(f'{settings.api_prefix}/auth/'):
                for operation in operations.values():
                    operation.get('responses', {}).pop('422', None)
        return schema

    app.openapi = documented_openapi
    app.add_middleware(AuthLimitMiddleware, prefix=f'{settings.api_prefix}/auth/')
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
        if is_auth:
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

    return app


app = create_app()
