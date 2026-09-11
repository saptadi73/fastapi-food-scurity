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
from app.core.database.session import close_database
from app.core.responses.envelope import Envelope, envelope

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
        description="Fondasi backend FSOS. Modul bisnis belum diimplementasikan.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Correlation-ID"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request.state.request_id = str(uuid4())
        request.state.correlation_id = request.headers.get(
            "X-Correlation-ID", request.state.request_id
        )[:128]
        request.state.started_at = perf_counter()
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

    return app


app = create_app()
