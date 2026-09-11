from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from fastapi import Request
from pydantic import BaseModel, Field


class Meta(BaseModel):
    request_id: str
    correlation_id: str
    timestamp: datetime
    execution_time_ms: float


class Envelope(BaseModel):
    success: bool
    code: int
    message: str
    data: Any = None
    errors: list[dict[str, Any]] = Field(default_factory=list)
    meta: Meta


def envelope(
    request: Request,
    *,
    code: int = 200,
    message: str = "Success",
    data: Any = None,
    errors: list[dict[str, Any]] | None = None,
) -> Envelope:
    return Envelope(
        success=code < 400,
        code=code,
        message=message,
        data=data,
        errors=errors or [],
        meta=Meta(
            request_id=request.state.request_id,
            correlation_id=request.state.correlation_id,
            timestamp=datetime.now(UTC),
            execution_time_ms=round(
                (perf_counter() - request.state.started_at) * 1000, 3
            ),
        ),
    )
