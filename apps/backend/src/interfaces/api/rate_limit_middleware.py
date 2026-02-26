import logging

from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.domain.ratelimit.rate_limiter_service import RateLimiterService
from src.infrastructure.ratelimit.config_loader import RateLimitConfigLoader

logger = logging.getLogger(__name__)

ENDPOINT_GROUP_MAP: dict[str, str | None] = {
    "/api/v1/webhook": "webhook",
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


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        rate_limiter: RateLimiterService,
        config_loader: RateLimitConfigLoader,
        jwt_secret_key: str,
        jwt_algorithm: str = "HS256",
        global_rpm: int = 1000,
    ) -> None:
        super().__init__(app)
        self._rate_limiter = rate_limiter
        self._config_loader = config_loader
        self._jwt_secret_key = jwt_secret_key
        self._jwt_algorithm = jwt_algorithm
        self._global_rpm = global_rpm

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path
        endpoint_group = _resolve_endpoint_group(path)

        if endpoint_group is None:
            return await call_next(request)

        identity = self._extract_identity(request)
        tenant_id = identity.get("tenant_id")
        user_id = identity.get("user_id")
        client_ip = identity.get("client_ip", "unknown")

        config = await self._config_loader.get_config(tenant_id, endpoint_group)

        # Multi-layer checks: global → tenant/IP → user
        checks = []

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
        for key, limit in checks:
            result = await self._rate_limiter.check_rate_limit(
                key, limit, WINDOW_SECONDS
            )
            if not result.allowed:
                retry_after = result.retry_after or 1
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": (
                            "Rate limit exceeded."
                            f" Try again in {retry_after} seconds."
                        )
                    },
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(limit),
                        "X-RateLimit-Remaining": "0",
                    },
                )
            min_remaining = min(min_remaining, result.remaining)

        response = await call_next(request)
        if min_remaining != float("inf"):
            response.headers["X-RateLimit-Remaining"] = str(int(min_remaining))
        return response

    def _extract_identity(self, request: Request) -> dict:
        """Lightweight JWT decode to extract tenant_id/user_id. No auth enforcement."""
        result: dict = {
            "client_ip": request.client.host if request.client else "unknown",
        }

        auth_header = request.headers.get("authorization", "")
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
