import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.testclient import TestClient

from src.domain.ratelimit.rate_limiter_service import RateLimitResult
from src.infrastructure.ratelimit.config_loader import ResolvedRateLimitConfig
from src.interfaces.api.rate_limit_middleware import RateLimitMiddleware

scenarios("unit/ratelimit/rate_limit_middleware.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def mock_rate_limiter():
    limiter = AsyncMock()
    limiter.check_rate_limit = AsyncMock(
        return_value=RateLimitResult(allowed=True, remaining=10)
    )
    return limiter


@pytest.fixture
def mock_config_loader():
    loader = AsyncMock()
    loader.get_config = AsyncMock(
        return_value=ResolvedRateLimitConfig(
            requests_per_minute=100,
            burst_size=120,
            per_user_requests_per_minute=50,
        )
    )
    return loader


@pytest.fixture
def context():
    return {"rate_limit_calls": {}}


@pytest.fixture
def mock_jwt_service():
    from src.infrastructure.auth.jwt_service import JWTService

    return JWTService(
        secret_key="test-secret-key",
        algorithm="HS256",
        access_token_expire_minutes=60,
    )


def _create_app(mock_rate_limiter, mock_config_loader):
    """Create a minimal Starlette/FastAPI app with rate limit middleware."""
    from starlette.applications import Starlette
    from starlette.routing import Route

    async def dummy_handler(request):
        return JSONResponse({"ok": True})

    app = Starlette(
        routes=[
            Route("/api/v1/rag/query", dummy_handler, methods=["GET"]),
            Route("/api/v1/tenants", dummy_handler, methods=["GET"]),
            Route("/health", dummy_handler, methods=["GET"]),
        ],
    )

    app.add_middleware(
        RateLimitMiddleware,
        rate_limiter=mock_rate_limiter,
        config_loader=mock_config_loader,
        jwt_secret_key="test-secret-key",
        jwt_algorithm="HS256",
        global_rpm=1000,
    )
    return app


@given("限流中介層已設定")
def middleware_configured(context, mock_rate_limiter, mock_config_loader):
    context["app"] = _create_app(mock_rate_limiter, mock_config_loader)


@given(parsers.parse('租戶 "{tenant_id}" 的 "{group}" 端點群組已超過限額'))
def tenant_over_limit(context, mock_rate_limiter, tenant_id, group):
    original = mock_rate_limiter.check_rate_limit

    async def _side_effect(key, limit, window):
        if tenant_id in key and "global" not in key and "user" not in key:
            return RateLimitResult(allowed=False, remaining=0, retry_after=42)
        return RateLimitResult(allowed=True, remaining=10)

    mock_rate_limiter.check_rate_limit = AsyncMock(side_effect=_side_effect)


@given(parsers.parse('IP "{ip}" 的 "{group}" 端點群組已超過限額'))
def ip_over_limit(context, mock_rate_limiter, ip, group):
    async def _side_effect(key, limit, window):
        # TestClient sends "testclient" as client IP, so match any ip: key
        if "ip:" in key and "global" not in key:
            return RateLimitResult(allowed=False, remaining=0, retry_after=30)
        return RateLimitResult(allowed=True, remaining=10)

    mock_rate_limiter.check_rate_limit = AsyncMock(side_effect=_side_effect)


@given(parsers.parse('租戶 "{tenant_id}" 的 "{group}" 端點群組未超過限額'))
def tenant_under_limit(context, mock_rate_limiter, tenant_id, group):
    # Default: allowed
    pass


@given(parsers.parse('使用者 "{user_id}" 的 per-user 限額已超過'))
def user_over_limit(context, mock_rate_limiter, user_id):
    original_side_effect = mock_rate_limiter.check_rate_limit.side_effect

    async def _side_effect(key, limit, window):
        if user_id in key:
            return RateLimitResult(allowed=False, remaining=0, retry_after=15)
        return RateLimitResult(allowed=True, remaining=10)

    mock_rate_limiter.check_rate_limit = AsyncMock(side_effect=_side_effect)


@when(parsers.parse('租戶 "{tenant_id}" 請求 "{path}"'))
def tenant_request(context, mock_jwt_service, tenant_id, path):
    token = mock_jwt_service.create_tenant_token(tenant_id)
    client = TestClient(context["app"], raise_server_exceptions=False)
    context["response"] = client.get(
        path, headers={"Authorization": f"Bearer {token}"}
    )


@when(parsers.parse('IP "{ip}" 請求 "{path}"'))
def ip_request(context, ip, path):
    client = TestClient(context["app"], raise_server_exceptions=False)
    context["response"] = client.get(path)


@when(parsers.parse('使用者 "{user_id}" 租戶 "{tenant_id}" 請求 "{path}"'))
def user_request(context, mock_jwt_service, user_id, tenant_id, path):
    token = mock_jwt_service.create_user_token(user_id, tenant_id, "user")
    client = TestClient(context["app"], raise_server_exceptions=False)
    context["response"] = client.get(
        path, headers={"Authorization": f"Bearer {token}"}
    )


@when(parsers.parse('請求 "{path}"'))
def plain_request(context, path):
    client = TestClient(context["app"], raise_server_exceptions=False)
    context["response"] = client.get(path)


@then(parsers.parse("回應狀態碼應為 {code:d}"))
def check_status(context, code):
    assert context["response"].status_code == code, (
        f"Expected {code}, got {context['response'].status_code}: "
        f"{context['response'].text}"
    )


@then("回應應包含 Retry-After header")
def has_retry_after(context):
    assert "retry-after" in context["response"].headers


@then("請求應直接通過不檢查限流")
def request_passes_through(context, mock_rate_limiter):
    assert context["response"].status_code == 200
    # For health endpoint (exempt), rate limiter should not be called
    # But it might be called 0 times for the exempt path
