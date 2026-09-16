"""Issue #98 步驟 8–11。
金額精度 / opaque 標記 / X-Client-Version / SSE id / widget 非串流。"""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from pytest_bdd import given, parsers, scenarios, then, when

from src.interfaces.api import widget_router
from src.interfaces.api._stream_events import sse_frame
from src.interfaces.api.client_version_middleware import ClientVersionMiddleware
from src.interfaces.api.conversation_router import MessageResponse
from src.interfaces.api.types import ApiMoney

scenarios("unit/interfaces/api_contract_batch2.feature")


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


# ── ApiMoney ──────────────────────────────────────────────────


class _Money(BaseModel):
    v: ApiMoney


@when(parsers.parse("以 ApiMoney 序列化 {raw}"))
def serialize_money(ctx, raw):
    ctx["out"] = json.loads(_Money(v=float(raw)).model_dump_json())["v"]


@then(parsers.parse("金額序列化結果為 {expected}"))
def assert_money(ctx, expected):
    assert ctx["out"] == float(expected)


def _collect_refs(node, acc: set[str]) -> None:
    if isinstance(node, dict):
        if "$ref" in node:
            acc.add(node["$ref"].split("/")[-1])
        for v in node.values():
            _collect_refs(v, acc)
    elif isinstance(node, list):
        for v in node:
            _collect_refs(v, acc)


def _response_schemas(spec: dict) -> dict[str, dict]:
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
            return {n: schemas[n] for n in names if n in schemas}


@when("掃描全部回應模型的金額欄位")
def scan_money(ctx, api_app):
    import re

    missing = []
    for name, sc in _response_schemas(api_app.openapi()).items():
        for fname, prop in sc.get("properties", {}).items():
            subs = [prop] + prop.get("anyOf", [])
            is_money = re.search(r"cost|price|amount", fname, re.I)
            if is_money and any(s.get("type") == "number" for s in subs):
                if not any(s.get("x-precision") for s in subs):
                    missing.append(f"{name}.{fname}")
    ctx["missing"] = missing


@then("每個名稱含 cost、price、amount 的 number 欄位都有 x-precision")
def assert_money_marked(ctx):
    assert ctx["missing"] == [], ctx["missing"]


@when(parsers.parse("以 estimated_cost {raw} 建立 TokenUsageResponse 並序列化"))
def usage_response(ctx, raw):
    from src.interfaces.api.agent_router import TokenUsageResponse

    m = TokenUsageResponse(
        model="m", input_tokens=1, output_tokens=1, total_tokens=2,
        estimated_cost=float(raw),
    )
    ctx["dump"] = json.loads(m.model_dump_json())


@then(parsers.parse(
    '序列化含 estimated_cost {num} 與 estimated_cost_str "{text}"'
))
def assert_usage_dump(ctx, num, text):
    assert ctx["dump"]["estimated_cost"] == float(num)
    assert ctx["dump"]["estimated_cost_str"] == text


# ── opaque ────────────────────────────────────────────────────


@when("掃描全部回應模型的 object 欄位")
def scan_opaque(ctx, api_app):
    missing = []
    for name, sc in _response_schemas(api_app.openapi()).items():
        for fname, prop in sc.get("properties", {}).items():
            subs = [prop] + prop.get("anyOf", [])
            untyped = [
                s for s in subs
                if s.get("type") == "object" and not s.get("properties")
                and "$ref" not in s
                and not isinstance(s.get("additionalProperties"), dict)  # typed map
            ]
            marked = prop.get("x-opaque") or any(s.get("x-opaque") for s in subs)
            if untyped and not marked:
                missing.append(f"{name}.{fname}")
    ctx["missing"] = missing


@then("沒有任何未標 x-opaque 且無 properties 的 object 欄位")
def assert_opaque(ctx):
    assert ctx["missing"] == [], ctx["missing"]


@when("取得 MessageResponse 的 JSON schema")
def message_schema(ctx):
    ctx["schema"] = MessageResponse.model_json_schema(mode="serialization")


@then("structured_content 引用 HistoryStructuredContent 且含 contact、sources、output")
def assert_history_typed(ctx):
    prop = ctx["schema"]["properties"]["structured_content"]
    refs = [s.get("$ref", "") for s in prop.get("anyOf", [prop])]
    assert any(r.endswith("/HistoryStructuredContent") for r in refs), prop
    fields = ctx["schema"]["$defs"]["HistoryStructuredContent"]["properties"]
    assert {"contact", "sources", "output"} <= set(fields)


# ── X-Client-Version ──────────────────────────────────────────


@given(parsers.parse('最低客戶端版本設定為 "{minimum}"'))
def version_app(ctx, minimum):
    minimum = "" if minimum == "(none)" else minimum
    app = FastAPI()

    @app.get("/api/v1/health")
    async def health():
        return {"status": "ok"}

    app.add_middleware(ClientVersionMiddleware, min_version=minimum)
    ctx["client"] = TestClient(app, raise_server_exceptions=False)


@when(parsers.parse('帶 X-Client-Version "{header}" 打健康檢查'))
def call_health(ctx, header):
    headers = {} if header == "(none)" else {"X-Client-Version": header}
    ctx["resp"] = ctx["client"].get("/api/v1/health", headers=headers)


@then(parsers.parse("狀態碼為 {status:d}"))
def assert_status(ctx, status):
    assert ctx["resp"].status_code == status, ctx["resp"].text


@then('錯誤 body 的 code 為 "client_upgrade_required" 且帶 min_client_version')
def assert_426_body(ctx):
    body = ctx["resp"].json()
    assert body["code"] == "client_upgrade_required"
    assert body["min_client_version"] == "2.0.0"
    assert isinstance(body["detail"], str)


# ── SSE id ────────────────────────────────────────────────────


@when("把三個事件經 sse_frame 編碼")
def encode_frames(ctx):
    ctx["frames"] = [
        sse_frame({"type": "token", "content": "a"}, i) for i in (1, 2, 3)
    ]


@then("三個 frame 依序帶 id 1、2、3 且以空行結尾")
def assert_frames(ctx):
    for i, frame in enumerate(ctx["frames"], 1):
        assert frame.startswith(f"id: {i}\ndata: "), frame
        assert frame.endswith("\n\n")
        assert json.loads(frame.split("data: ", 1)[1].strip())["type"] == "token"


# ── widget 非串流 ─────────────────────────────────────────────


@when("檢查 widget_router 的路由")
def widget_routes(ctx):
    ctx["routes"] = {
        (r.path, tuple(sorted(r.methods or ()))): r
        for r in widget_router.router.routes
    }


@then('存在 POST "/{short_code}/chat" 且回應模型為 WidgetChatResponse')
def assert_widget_chat(ctx):
    route = ctx["routes"].get(("/api/v1/widget/{short_code}/chat", ("POST",)))
    assert route is not None, sorted(ctx["routes"])
    assert route.response_model.__name__ == "WidgetChatResponse"
