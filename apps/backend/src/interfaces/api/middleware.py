"""HTTP middleware: request-id tracking + structured logging.

Uses pure ASGI instead of BaseHTTPMiddleware to avoid breaking
ContextVar propagation for streaming responses.  BaseHTTPMiddleware
runs the inner app in a separate anyio task, so ContextVars set by
outer middleware (e.g. SessionCleanupMiddleware) are copied — but
changes made inside the child task are invisible to the parent.
This causes DB sessions created during streaming to be orphaned
("idle in transaction" leak).
"""

import asyncio
import base64
import json
import time
import uuid

import structlog
from starlette.types import ASGIApp, Receive, Scope, Send

from src.infrastructure.logging import get_logger
from src.infrastructure.logging.error_context import (
    get_captured_error,
    reset_captured_error,
)
from src.infrastructure.logging.request_log_writer import write_request_log
from src.infrastructure.logging.trace import flush_trace, init_trace

logger = get_logger(__name__)

WIDGET_PATH_PREFIX = "/api/v1/widget/"
STATIC_PATH_PREFIX = "/static/"
_STREAM_SUFFIXES = ("/stream", "/export")
_LONG_TIMEOUT_PATTERNS = ("/documents",)  # upload + background OCR


class RequestTimeoutMiddleware:
    """Pure ASGI middleware — enforce per-request timeout.

    Streaming endpoints (paths ending with /stream or /export) get a
    longer timeout. Returns 504 Gateway Timeout on expiry.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        timeout: int = 30,
        stream_timeout: int = 180,
    ) -> None:
        self._app = app
        self._timeout = timeout
        self._stream_timeout = stream_timeout

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        path = scope.get("path", "")
        is_stream = any(path.endswith(s) for s in _STREAM_SUFFIXES)
        is_long = any(p in path for p in _LONG_TIMEOUT_PATTERNS)
        limit = self._stream_timeout if (is_stream or is_long) else self._timeout

        try:
            async with asyncio.timeout(limit):
                await self._app(scope, receive, send)
        except TimeoutError:
            logger.warning(
                "request.timeout",
                path=path,
                method=scope.get("method", ""),
                timeout_seconds=limit,
            )
            await send({
                "type": "http.response.start",
                "status": 504,
                "headers": [
                    (b"content-type", b"application/json"),
                ],
            })
            body = json.dumps({"detail": "Request timeout"}).encode()
            await send({
                "type": "http.response.body",
                "body": body,
            })


class CORSMiddlewareWithExclusions:
    """Pure ASGI wrapper — bypasses CORSMiddleware for excluded paths.

    Widget endpoints handle their own dynamic CORS based on
    ``bot.widget_allowed_origins``, so they must not be intercepted
    by the global CORS middleware.

    Static files (``/static/``) are served with permissive CORS
    (``Access-Control-Allow-Origin: *``) so that widget embeds on
    any domain can load models, textures, and scripts.
    """

    def __init__(self, app: ASGIApp, **cors_kwargs: object) -> None:
        from starlette.middleware.cors import CORSMiddleware

        self._app = app
        self._cors = CORSMiddleware(app, **cors_kwargs)  # type: ignore[arg-type]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._cors(scope, receive, send)
            return

        path = scope.get("path", "")

        if path.startswith(WIDGET_PATH_PREFIX):
            # Widget API handles its own CORS
            await self._app(scope, receive, send)
        elif path.startswith(STATIC_PATH_PREFIX):
            # Static files: permissive CORS
            await self._serve_static_with_cors(scope, receive, send)
        else:
            await self._cors(scope, receive, send)

    async def _serve_static_with_cors(
        self, scope: Scope, receive: Receive, send: Send,
    ) -> None:
        """Wrap static file responses with Access-Control-Allow-Origin: *."""

        async def send_with_cors(message: object) -> None:
            if isinstance(message, dict) and message.get("type") == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"access-control-allow-origin", b"*"))
                message = {**message, "headers": headers}
            await send(message)  # type: ignore[arg-type]

        await self._app(scope, receive, send_with_cors)


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


class RequestIDMiddleware:
    """Pure ASGI middleware — injects request_id, logs request/response.

    Unlike BaseHTTPMiddleware this runs in the SAME task as the outer
    middleware chain, so ContextVar-based session tracking works correctly
    even for StreamingResponse endpoints.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # --- request phase ---
        headers = dict(scope.get("headers", []))
        request_id = (
            headers.get(b"x-request-id", b"").decode()
            or uuid.uuid4().hex[:12]
        )
        method = scope.get("method", "")
        path = scope.get("path", "")

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            api=f"{method} {path}",
        )

        logger.info("http.request")

        tenant_id = extract_tenant_id(
            headers.get(b"authorization", b"").decode()
        )

        init_trace()
        start = time.perf_counter()

        # Capture status_code from response start message
        status_code = 500  # default if we never see response.start

        async def send_wrapper(message: dict) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                # Inject X-Request-ID header
                raw_headers = list(message.get("headers", []))
                raw_headers.append(
                    (b"x-request-id", request_id.encode())
                )
                message = {**message, "headers": raw_headers}
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
            trace_steps = flush_trace(elapsed_ms)

            error_detail = get_captured_error()
            reset_captured_error()

            logger.info(
                "http.response",
                status_code=status_code,
                elapsed_ms=elapsed_ms,
            )

            if not path.startswith("/api/v1/logs"):
                asyncio.create_task(
                    write_request_log(
                        request_id=request_id,
                        method=method,
                        path=path,
                        status_code=status_code,
                        elapsed_ms=elapsed_ms,
                        trace_steps=trace_steps,
                        tenant_id=tenant_id,
                        error_detail=error_detail,
                    )
                )

                if error_detail:
                    from src.infrastructure.logging.error_event_writer import (
                        write_error_event,
                    )

                    asyncio.create_task(
                        write_error_event(
                            error_detail=error_detail,
                            request_id=request_id,
                            method=method,
                            path=path,
                            status_code=status_code,
                            tenant_id=tenant_id,
                        )
                    )
