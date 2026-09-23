"""Fence（Issue #67）：所有 API 端點預設必須掛認證，公開端點要顯式列名。

背景：providers / mcp-servers / bots/{id}/workers / error-events 四個入口整支或
單條沒有 `get_current_tenant` / `require_role`，一路留到 POC 對外開放。
認證是「每支 router 自己記得掛」的東西，這個測試把它變成結構性的預設拒絕：

- 端點若沒有任何認證相依，必須出現在 PUBLIC_ROUTES 並附理由。
- PUBLIC_ROUTES 若有端點其實已掛認證，也 fail（清單要誠實）。
"""

import pytest
from fastapi.routing import APIRoute

# 認證相依的 __qualname__；新增認證方式（例如 widget token）要一併登記
AUTH_DEPENDENCIES = {
    "get_current_tenant",
    "require_role.<locals>._check",
    "require_scope.<locals>._check",
    "get_usage_context",
    "require_owned_bot",
    "get_widget_principal",
}

# (method, path) → 理由。沒有理由的公開端點不准存在。
_PREFLIGHT = "CORS preflight"
_LINE = "LINE webhook, HMAC signature"

PUBLIC_ROUTES: dict[tuple[str, str], str] = {
    ("POST", "/api/v1/auth/login"): "login itself",
    ("POST", "/api/v1/auth/refresh"): "refresh token in body",
    ("POST", "/api/v1/auth/token"): "client_credentials exchange",
    ("GET", "/api/v1/health"): "health check",
    ("POST", "/api/v1/webhook/line"): _LINE,
    ("POST", "/api/v1/webhook/line/{bot_short_code}"): _LINE,
    ("OPTIONS", "/api/v1/widget/{short_code}/chat/stream"): _PREFLIGHT,
    ("OPTIONS", "/api/v1/widget/{short_code}/config"): _PREFLIGHT,
    ("OPTIONS", "/api/v1/widget/{short_code}/error"): _PREFLIGHT,
    ("OPTIONS", "/api/v1/widget/{short_code}/feedback"): _PREFLIGHT,
    ("OPTIONS", "/api/v1/widget/{short_code}/identify"): _PREFLIGHT,
    ("GET", "/api/v1/widget/{short_code}/config"): "widget entry, issues token",
    ("GET", "/{full_path:path}"): "admin SPA fallback",
}

# 依部署產物有條件掛載的公開路由：不存在時不算清單過期。
# admin SPA 只在 static/admin/index.html 存在時掛（_mount_admin_spa；CI 的後端 job
# 不建前端，Package 階段才 build:embed）。由 test_admin_spa_fallback_is_public
# 以暫存目錄強制掛載，確保 CI 上也驗得到它。
CONDITIONAL_ROUTES = {("GET", "/{full_path:path}")}


@pytest.fixture(scope="module")
def app():
    mp = pytest.MonkeyPatch()
    mp.setenv("E2E_MODE", "true")
    mp.setenv("OPENAI_API_KEY", "sk-test-fake")
    from src.main import create_app

    yield create_app(skip_rate_limit=True)
    mp.undo()


def _dependency_names(dependant, acc: set[str]) -> set[str]:
    for sub in dependant.dependencies:
        acc.add(getattr(sub.call, "__qualname__", type(sub.call).__name__))
        _dependency_names(sub, acc)
    return acc


def _iter_api_routes(routes):
    for r in routes:
        if isinstance(r, APIRoute):
            yield r
        elif hasattr(r, "original_router"):  # FastAPI _IncludedRouter
            yield from _iter_api_routes(r.original_router.routes)
        elif hasattr(r, "routes"):
            yield from _iter_api_routes(r.routes)


def _classify(app):
    unauth: set[tuple[str, str]] = set()
    authed: set[tuple[str, str]] = set()
    for route in _iter_api_routes(app.routes):
        names = _dependency_names(route.dependant, set())
        for method in route.methods:
            key = (method, route.path)
            (authed if names & AUTH_DEPENDENCIES else unauth).add(key)
    return unauth, authed


def test_every_endpoint_is_authenticated_or_explicitly_public(app):
    unauth, _ = _classify(app)
    leaked = sorted(unauth - set(PUBLIC_ROUTES))
    assert leaked == [], (
        "endpoints without auth dependency and not in PUBLIC_ROUTES: "
        f"{leaked}"
    )


def test_public_route_list_is_honest(app):
    unauth, authed = _classify(app)
    stale = sorted(set(PUBLIC_ROUTES) & authed)
    assert stale == [], f"PUBLIC_ROUTES entries that now require auth: {stale}"
    missing = sorted(set(PUBLIC_ROUTES) - unauth - authed - CONDITIONAL_ROUTES)
    assert missing == [], f"PUBLIC_ROUTES entries that no longer exist: {missing}"


def test_scan_covers_the_api_surface(app):
    unauth, authed = _classify(app)
    assert len(unauth | authed) > 150, "route scan lost the included routers"


def test_admin_spa_fallback_is_public(tmp_path):
    """不依賴本機有沒有 build 過前端：用暫存目錄強制掛上 SPA fallback 再分類。"""
    from fastapi import FastAPI

    from src.main import _mount_admin_spa

    (tmp_path / "admin").mkdir()
    (tmp_path / "admin" / "index.html").write_text("<html></html>")
    spa_app = FastAPI()
    _mount_admin_spa(spa_app, str(tmp_path))

    unauth, authed = _classify(spa_app)
    assert CONDITIONAL_ROUTES <= unauth, "SPA fallback 應掛載且不帶認證相依"
    assert CONDITIONAL_ROUTES <= set(PUBLIC_ROUTES)
    assert not authed

