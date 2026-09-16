"""Issue #97：契約改造第一批。
日期 profile / 錯誤 schema / 錯誤碼 fence / OpenAPI 快照 / CORS。"""

import json
import pathlib
import re
from datetime import datetime

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel
from pytest_bdd import parsers, scenarios, then, when

from src.interfaces.api.errors import API_ERROR_RESPONSES
from src.interfaces.api.types import API_DATETIME_PATTERN, ApiDateTime

scenarios("unit/interfaces/api_contract_batch1.feature")

ROUTER_DIR = pathlib.Path(__file__).resolve().parents[3] / "src" / "interfaces" / "api"
REPO_ROOT = pathlib.Path(__file__).resolve().parents[5]
OUTWARD_ROUTERS = [
    "auth_router.py", "api_key_router.py", "bot_router.py",
    "knowledge_base_router.py", "document_router.py", "conversation_router.py",
]


@pytest.fixture
def ctx():
    return {}


@pytest.fixture(scope="module")
def api_app():
    mp = pytest.MonkeyPatch()
    mp.setenv("E2E_MODE", "true")
    mp.setenv("OPENAI_API_KEY", "sk-test-fake")
    from src.main import create_app

    yield create_app(skip_rate_limit=True)
    mp.undo()


class _DtModel(BaseModel):
    at: ApiDateTime


# ── ApiDateTime ────────────────────────────────────────────────


@when(parsers.parse("以 ApiDateTime 序列化 {raw}"))
def serialize_dt(ctx, raw):
    if raw.endswith("(naive)"):
        value = datetime.fromisoformat(raw.replace(" (naive)", ""))
    else:
        value = datetime.fromisoformat(raw)
    ctx["out"] = json.loads(_DtModel(at=value).model_dump_json())["at"]


@then(parsers.parse('序列化結果為 "{expected}"'))
def assert_dt(ctx, expected):
    assert ctx["out"] == expected


@then("序列化結果符合 API_DATETIME_PATTERN")
def assert_pattern(ctx):
    assert re.match(API_DATETIME_PATTERN, ctx["out"])


@when("取得含 ApiDateTime 欄位的模型 JSON schema")
def dt_schema(ctx):
    ctx["schema"] = _DtModel.model_json_schema(mode="serialization")["properties"]["at"]


@then('該欄位的 schema 含 format "date-time" 與 API_DATETIME_PATTERN')
def assert_dt_schema(ctx):
    assert ctx["schema"]["format"] == "date-time"
    assert ctx["schema"]["pattern"] == API_DATETIME_PATTERN


def _collect_refs(node, acc: set[str]) -> None:
    if isinstance(node, dict):
        if "$ref" in node:
            acc.add(node["$ref"].split("/")[-1])
        for v in node.values():
            _collect_refs(v, acc)
    elif isinstance(node, list):
        for v in node:
            _collect_refs(v, acc)


def _response_schema_names(spec: dict) -> set[str]:
    """回應直接或間接引用到的 schema 名稱（遞移閉包）。"""
    names: set[str] = set()
    for item in spec["paths"].values():
        for op in item.values():
            if isinstance(op, dict):
                _collect_refs(op.get("responses", {}), names)
    schemas = spec["components"]["schemas"]
    while True:
        before = len(names)
        for n in list(names):
            _collect_refs(schemas.get(n, {}), names)
        if len(names) == before:
            return names


@when("掃描全部回應模型的 JSON schema")
def scan_dt(ctx, api_app):
    spec = api_app.openapi()
    schemas = spec["components"]["schemas"]
    missing = []
    for name in sorted(_response_schema_names(spec)):
        for fname, prop in schemas.get(name, {}).get("properties", {}).items():
            for sub in [prop] + prop.get("anyOf", []):
                is_dt = sub.get("format") == "date-time"
                if is_dt and sub.get("pattern") != API_DATETIME_PATTERN:
                    missing.append(f"{name}.{fname}")
    ctx["missing"] = missing


@then("沒有任何 date-time 欄位缺少 API_DATETIME_PATTERN")
def assert_no_missing(ctx):
    assert ctx["missing"] == [], ctx["missing"]


# ── 錯誤 schema ───────────────────────────────────────────────


class _Body(BaseModel):
    message: str


@pytest.fixture
def error_app():
    app = FastAPI(responses=API_ERROR_RESPONSES)

    @app.post("/thing")
    async def thing(body: _Body):
        raise HTTPException(status_code=404, detail="not_found")

    return app


@when("取得該應用的 OpenAPI", target_fixture="spec")
def get_spec(error_app):
    return error_app.openapi()


@pytest.fixture
def _declared_app(error_app):
    return error_app


@then("端點的 401 與 404 回應引用 ErrorResponse")
def assert_error_refs(spec):
    responses = spec["paths"]["/thing"]["post"]["responses"]
    for code in ("401", "404"):
        ref = responses[code]["content"]["application/json"]["schema"]["$ref"]
        assert ref.endswith("/ErrorResponse"), responses[code]


@then("端點的 422 回應引用 ValidationErrorResponse 而非 HTTPValidationError")
def assert_422_ref(spec):
    r422 = spec["paths"]["/thing"]["post"]["responses"]["422"]
    ref = r422["content"]["application/json"]["schema"]["$ref"]
    assert ref.endswith("/ValidationErrorResponse"), ref


# 「Given 一個宣告了 API_ERROR_RESPONSES 的測試應用」由 error_app fixture 提供
from pytest_bdd import given  # noqa: E402


@given("一個宣告了 API_ERROR_RESPONSES 的測試應用")
def given_error_app(error_app):
    return error_app


# ── 錯誤碼 fence ──────────────────────────────────────────────


@when(
    "掃描 auth、api_key、bot、knowledge_base、document、conversation 六支 router 原始碼"
)
def scan_routers(ctx):
    hits = []
    for name in OUTWARD_ROUTERS:
        src = (ROUTER_DIR / name).read_text()
        for i, line in enumerate(src.splitlines(), 1):
            if "raise HTTPException(" in line or "return HTTPException(" in line:
                hits.append(f"{name}:{i}")
    ctx["hits"] = hits


@then('沒有任何 "raise HTTPException(" 出現')
def assert_no_http_exception(ctx):
    assert ctx["hits"] == [], ctx["hits"]


# ── OpenAPI 快照 ──────────────────────────────────────────────


@when("以 create_app 產出 OpenAPI 並與 docs/api/openapi.json 比對")
def compare_snapshot(ctx, api_app):
    generated = api_app.openapi()
    committed = json.loads((REPO_ROOT / "docs" / "api" / "openapi.json").read_text())
    ctx["same"] = generated == committed
    if not ctx["same"]:
        g_paths, c_paths = set(generated["paths"]), set(committed["paths"])
        ctx["diff_hint"] = {
            "only_generated": sorted(g_paths - c_paths)[:5],
            "only_committed": sorted(c_paths - g_paths)[:5],
        }


@then("兩者完全相同")
def assert_snapshot(ctx):
    assert ctx["same"], (
        "docs/api/openapi.json 過期，請執行 `make openapi` 重新產出；"
        f"提示：{ctx.get('diff_hint')}"
    )


# ── CORS ──────────────────────────────────────────────────────


@when("帶 Origin 對 /api/v1/health 送 GET")
def cors_get(ctx, api_app):
    client = TestClient(api_app, raise_server_exceptions=False)
    ctx["resp"] = client.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})


@then(parsers.parse("回應的 Access-Control-Expose-Headers 含 {names}"))
def assert_expose(ctx, names):
    raw = ctx["resp"].headers.get("access-control-expose-headers", "")
    exposed = {h.strip().lower() for h in raw.split(",")}
    for n in re.findall(r'"([^"]+)"', names):
        assert n.lower() in exposed, (n, exposed)
