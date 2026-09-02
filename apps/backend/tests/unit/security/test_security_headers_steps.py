"""安全標頭中介層 + docs 關閉 BDD Step Definitions（security-precheck 2026-09-02）"""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from starlette.applications import Starlette
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from src.interfaces.api.security_headers_middleware import SecurityHeadersMiddleware
from src.main import docs_kwargs_for_env

scenarios("unit/security/security_headers.feature")


@pytest.fixture
def context():
    return {}


@given("掛上安全標頭中介層的應用")
def app_with_headers(context):
    async def ok(_request):
        return JSONResponse({"ok": True})

    async def cached(_request):
        return JSONResponse(
            {"ok": True}, headers={"Cache-Control": "private, max-age=60"}
        )

    async def static(_request):
        return PlainTextResponse("console.log('w')")

    app = Starlette(routes=[
        Route("/admin/", ok),
        Route("/api/v1/things", ok),
        Route("/api/v1/cached", cached),
        Route("/static/widget.js", static),
    ])
    app.add_middleware(SecurityHeadersMiddleware)
    context["client"] = TestClient(app)


@when(parsers.parse('請求 "{path}"'))
def do_request(context, path):
    context["resp"] = context["client"].get(path)


@then(parsers.parse('回應標頭 "{name}" 應含 "{value}"'))
def header_contains(context, name, value):
    assert value in context["resp"].headers.get(name, ""), dict(context["resp"].headers)


@then(parsers.parse('回應標頭 "{name}" 應為 "{value}"'))
def header_equals(context, name, value):
    assert context["resp"].headers.get(name) == value, dict(context["resp"].headers)


@then(parsers.parse('回應不應有標頭 "{name}" 值為 "{value}"'))
def header_not_value(context, name, value):
    assert context["resp"].headers.get(name) != value


@when(parsers.parse('以 app_env "{env}" 計算 FastAPI 文件參數'))
def compute_docs(context, env):
    context["docs"] = docs_kwargs_for_env(env)


@then(parsers.parse("docs_url 應為 {value}"))
def docs_url_is(context, value):
    expected = None if value == "None" else value
    assert context["docs"]["docs_url"] == expected
    if expected is None:
        assert context["docs"]["redoc_url"] is None
        assert context["docs"]["openapi_url"] is None
