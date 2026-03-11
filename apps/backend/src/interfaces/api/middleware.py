"""HTTP middleware: request-id tracking + structured logging."""

import asyncio
import base64
import json
import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src.infrastructure.logging import get_logger
from src.infrastructure.logging.error_context import (
    get_captured_error,
    reset_captured_error,
)
from src.infrastructure.logging.request_log_writer import write_request_log
from src.infrastructure.logging.trace import flush_trace, init_trace

logger = get_logger(__name__)


def extract_tenant_id(authorization: str) -> str | None:
    """Extract tenant_id from a JWT Bearer token (base64, no verify)."""
    if not authorization.startswith("Bearer "):
        return None
    try:
        payload_b64 = authorization[7:].split(".")[1]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        token_type = payload.get("type", "")
        if token_type == "user_access":
            return payload.get("tenant_id")
        elif token_type == "tenant_access":
            return payload.get("sub")
    except Exception:
        pass
    return None


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

        # Extract tenant_id from JWT for logging
        tenant_id = extract_tenant_id(
            request.headers.get("authorization", "")
        )

        init_trace()
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
        trace_steps = flush_trace(elapsed_ms)

        # Read and reset captured error from ContextVar
        error_detail = get_captured_error()
        reset_captured_error()

        logger.info(
            "http.response",
            status_code=response.status_code,
            elapsed_ms=elapsed_ms,
        )

        # Fire-and-forget: persist request log (skip log viewer itself)
        if not request.url.path.startswith("/api/v1/logs"):
            asyncio.create_task(
                write_request_log(
                    request_id=request_id,
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    elapsed_ms=elapsed_ms,
                    trace_steps=trace_steps,
                    tenant_id=tenant_id,
                    error_detail=error_detail,
                )
            )

        response.headers["X-Request-ID"] = request_id
        return response
