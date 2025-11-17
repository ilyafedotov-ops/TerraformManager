from __future__ import annotations

from time import perf_counter
from typing import Callable, Awaitable
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from backend.utils.logging import get_logger, log_context


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Attach request metadata to the structured logging context and emit per-request entries."""

    def __init__(self, app):
        super().__init__(app)
        self.logger = get_logger(__name__)

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        start = perf_counter()
        client_ip = request.client.host if request.client else None
        with log_context(request_id=request_id, path=request.url.path, method=request.method):
            response: Response | None = None
            try:
                response = await call_next(request)
                return response
            finally:
                duration_ms = (perf_counter() - start) * 1000
                status_code = response.status_code if response else 500
                if response is not None:
                    response.headers.setdefault("X-Request-ID", request_id)
                self.logger.info(
                    "request completed",
                    extra={
                        "http": {
                            "method": request.method,
                            "path": request.url.path,
                            "status_code": status_code,
                            "duration_ms": round(duration_ms, 2),
                            "client_ip": client_ip,
                        },
                        "request_id": request_id,
                    },
                )
