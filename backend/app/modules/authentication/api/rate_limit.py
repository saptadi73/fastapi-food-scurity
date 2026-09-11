"""Bounded per-process fixed window; deployment across workers still needs a shared limiter."""
import math
from threading import Lock
from time import monotonic

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.responses.envelope import envelope


class AuthLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, prefix):
        super().__init__(app)
        self.prefix = prefix

    async def dispatch(self, request, call_next):
        if request.url.path.startswith(self.prefix) and request.method != 'OPTIONS':
            retry_after = request.app.state.auth_limiter.retry_after(request.client.host if request.client else 'unknown')
            if retry_after is not None:
                return JSONResponse(
                    envelope(request, code=429, message='Too many authentication requests').model_dump(mode='json'),
                    status_code=429, headers={'Retry-After': str(retry_after)},
                )
        return await call_next(request)


class AuthRateLimiter:
    def __init__(self, limit=100, window=60, max_clients=4096):
        self.limit, self.window, self.max_clients = limit, window, max_clients
        self._clients = {}
        self._lock = Lock()

    def retry_after(self, client: str) -> int | None:
        now = monotonic()
        with self._lock:
            self._clients = {key: value for key, value in self._clients.items() if value[0] > now}
            entry = self._clients.get(client)
            if entry is None:
                if len(self._clients) >= self.max_clients:
                    return max(1, math.ceil(min(v[0] for v in self._clients.values()) - now))
                entry = (now + self.window, 0)
            deadline, count = entry
            if count >= self.limit:
                return max(1, math.ceil(deadline - now))
            self._clients[client] = (deadline, count + 1)
            return None
