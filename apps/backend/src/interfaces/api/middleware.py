"""HTTP middleware: request-id tracking + structured logging."""

import asyncio
import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src.infrastructure.logging import get_logger
from src.infrastructure.logging.request_log_writer import write_request_log
from src.infrastructure.logging.trace import flush_trace, init_trace

logger = get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Inject request_id into structlog context and response header."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get(
            "X-Request-ID", uuid.uuid4().hex[:12]
        )
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            api=f"{request.method} {request.url.path}",
        )

        logger.info("http.request")

        init_trace()
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
        trace_steps = flush_trace(elapsed_ms)

        logger.info(
            "http.response",
            status_code=response.status_code,
            elapsed_ms=elapsed_ms,
        )

        # Fire-and-forget: persist request log asynchronously
        asyncio.create_task(
            write_request_log(
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                elapsed_ms=elapsed_ms,
                trace_steps=trace_steps,
            )
        )

        response.headers["X-Request-ID"] = request_id
        return response
