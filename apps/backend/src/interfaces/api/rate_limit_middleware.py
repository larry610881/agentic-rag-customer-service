"""Rate limit middleware — pure ASGI implementation.

Uses pure ASGI instead of BaseHTTPMiddleware to preserve ContextVar
propagation for streaming responses (same reason as RequestIDMiddleware).
"""

import json
import logging

from jose import JWTError, jwt
from starlette.types import ASGIApp, Receive, Scope, Send

from src.domain.ratelimit.rate_limiter_service import RateLimiterService
from src.infrastructure.logging.trace import trace_step
from src.infrastructure.ratelimit.config_loader import RateLimitConfigLoader

logger = logging.getLogger(__name__)

ENDPOINT_GROUP_MAP: dict[str, str | None] = {
    "/api/v1/webhook": "webhook",
    "/api/v1/widget": "widget",
    "/api/v1/rag": "rag",
    "/api/v1/agent": "rag",
    "/api/v1/feedback": "feedback",
    "/health": None,
    "/api/v1/auth": None,
}

WINDOW_SECONDS = 60


def _resolve_endpoint_group(path: str) -> str | None:
    """Map request path to endpoint group. Returns None for exempt paths."""
    for prefix, group in ENDPOINT_GROUP_MAP.items():
        if path.startswith(prefix):
            return group
    if path.startswith("/api/"):
        return "general"
    return None


class RateLimitMiddleware:
    """Pure ASGI rate-limit middleware.

    Checks multi-layer rate limits (global → tenant/IP → user) before
    forwarding the request.  On 429 it sends a JSON response directly
    via ASGI ``send``.
    """

    def __init__(
        self,
        app: ASGIApp,
        rate_limiter: RateLimiterService,
        config_loader: RateLimitConfigLoader,
        jwt_secret_key: str,
        jwt_algorithm: str = "HS256",
        global_rpm: int = 1000,
    ) -> None:
        self.app = app
        self._rate_limiter = rate_limiter
        self._config_loader = config_loader
        self._jwt_secret_key = jwt_secret_key
        self._jwt_algorithm = jwt_algorithm
        self._global_rpm = global_rpm

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path: str = scope.get("path", "")
        endpoint_group = _resolve_endpoint_group(path)

        if endpoint_group is None:
            await self.app(scope, receive, send)
            return

        identity = self._extract_identity(scope)
        tenant_id = identity.get("tenant_id")
        user_id = identity.get("user_id")
        client_ip = identity.get("client_ip", "unknown")

        with trace_step("rate_limit_config"):
            config = await self._config_loader.get_config(tenant_id, endpoint_group)

        # Multi-layer checks: global → tenant/IP → user
        checks: list[tuple[str, int]] = []

        # Layer 1: Global
        global_key = f"rl:global:{endpoint_group}:{WINDOW_SECONDS}"
        checks.append((global_key, self._global_rpm))

        # Layer 2: Tenant or IP
        if tenant_id:
            tenant_key = f"rl:{tenant_id}:{endpoint_group}:{WINDOW_SECONDS}"
            checks.append((tenant_key, config.requests_per_minute))
        else:
            ip_key = f"rl:ip:{client_ip}:{endpoint_group}:{WINDOW_SECONDS}"
            checks.append((ip_key, config.requests_per_minute))

        # Layer 3: Per-user
        if user_id and tenant_id and config.per_user_requests_per_minute:
            user_key = (
                f"rl:{tenant_id}:{user_id}:{endpoint_group}:{WINDOW_SECONDS}"
            )
            checks.append((user_key, config.per_user_requests_per_minute))

        # Execute checks — strictest wins
        min_remaining = float("inf")
        with trace_step("rate_limit_redis"):
            for key, limit in checks:
                result = await self._rate_limiter.check_rate_limit(
                    key, limit, WINDOW_SECONDS
                )
                if not result.allowed:
                    retry_after = result.retry_after or 1
                    await self._send_429(
                        send, retry_after, limit,
                    )
                    return
                min_remaining = min(min_remaining, result.remaining)

        # Inject X-RateLimit-Remaining header into response
        remaining_str = (
            str(int(min_remaining))
            if min_remaining != float("inf")
            else None
        )

        async def send_wrapper(message: dict) -> None:
            if message["type"] == "http.response.start" and remaining_str:
                raw_headers = list(message.get("headers", []))
                raw_headers.append(
                    (b"x-ratelimit-remaining", remaining_str.encode())
                )
                message = {**message, "headers": raw_headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _send_429(send: Send, retry_after: int, limit: int) -> None:
        body = json.dumps({
            "detail": (
                f"Rate limit exceeded. Try again in {retry_after} seconds."
            )
        }).encode()
        await send({
            "type": "http.response.start",
            "status": 429,
            "headers": [
                (b"content-type", b"application/json"),
                (b"retry-after", str(retry_after).encode()),
                (b"x-ratelimit-limit", str(limit).encode()),
                (b"x-ratelimit-remaining", b"0"),
            ],
        })
        await send({
            "type": "http.response.body",
            "body": body,
            "more_body": False,
        })

    def _extract_identity(self, scope: Scope) -> dict:
        """Lightweight JWT decode to extract tenant_id/user_id. No auth enforcement."""
        headers = dict(scope.get("headers", []))
        client = scope.get("client")
        result: dict = {
            "client_ip": client[0] if client else "unknown",
        }

        # Fallback identity: X-Visitor-Id header (widget anonymous users)
        visitor_id = headers.get(b"x-visitor-id", b"").decode()
        if visitor_id:
            result["user_id"] = f"visitor:{visitor_id}"

        auth_header = headers.get(b"authorization", b"").decode()
        if not auth_header.startswith("Bearer "):
            return result

        token = auth_header[7:]
        try:
            payload = jwt.decode(
                token,
                self._jwt_secret_key,
                algorithms=[self._jwt_algorithm],
            )
        except JWTError:
            return result

        token_type = payload.get("type", "tenant_access")
        if token_type == "user_access":
            result["user_id"] = payload.get("sub")
            result["tenant_id"] = payload.get("tenant_id")
        else:
            result["tenant_id"] = payload.get("sub")

        return result
