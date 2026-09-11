"""Issue #94：/agent/chat 對外契約加固的單元測試（Repository / use case 全 mock）。"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
import structlog
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from jose import jwt
from pydantic import BaseModel
from pytest_bdd import given, parsers, scenarios, then, when
from starlette.requests import Request

from src.application.usage.usage_context import UsageContext
from src.domain.agent.entity import AgentResponse
from src.infrastructure.auth.jwt_service import JWTService, TokenExpiredError
from src.interfaces.api.agent_router import (
    ChatRequest,
    _with_conversation_created,
    agent_chat,
)
from src.interfaces.api.deps import CurrentTenant
from src.interfaces.api.errors import ApiError, install_error_handlers

scenarios("unit/interfaces/chat_api_contract.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def ctx():
    return {}


# ── agent_chat 回應契約 ─────────────────────────────────────────────


def _use_case_returning(response: AgentResponse) -> AsyncMock:
    uc = AsyncMock()
    uc.execute = AsyncMock(return_value=response)
    return uc


@given(parsers.parse('一個回傳對話 id "{conv_id}" 的 SendMessage use case'))
def uc_conv(ctx, conv_id):
    ctx["uc"] = _use_case_returning(
        AgentResponse(answer="hi", conversation_id=conv_id)
    )


@given(parsers.parse("一個回傳結構化輸出 {payload} 的 SendMessage use case"))
def uc_structured(ctx, payload):
    parsed = json.loads(payload)
    ctx["expected_output"] = parsed
    ctx["uc"] = _use_case_returning(
        AgentResponse(
            answer=json.dumps(parsed, ensure_ascii=False),
            conversation_id="conv-json",
            structured_output=parsed,
        )
    )


@given(parsers.parse("一個回傳聯絡按鈕 {payload} 的 SendMessage use case"))
def uc_contact(ctx, payload):
    ctx["uc"] = _use_case_returning(
        AgentResponse(
            answer="請聯絡客服", conversation_id="c", contact=json.loads(payload)
        )
    )


@given("一個回傳純文字的 SendMessage use case")
def uc_plain(ctx):
    ctx["uc"] = _use_case_returning(AgentResponse(answer="純文字", conversation_id="c"))


def _call_chat(ctx, conversation_id: str | None):
    request = ChatRequest(message="q", bot_id="bot-1", conversation_id=conversation_id)
    http_request = Request({
        "type": "http", "headers": [], "client": ("127.0.0.1", 1234),
        "method": "POST", "path": "/",
    })
    tenant = CurrentTenant(
        tenant_id="t1", role="api_client", client_id="cid", scopes=("chat:send",)
    )
    ctx["resp"] = _run(
        agent_chat(
            request=request,
            http_request=http_request,
            tenant=tenant,
            use_case=ctx["uc"],
            record_usage=AsyncMock(),
            usage_ctx=UsageContext(),
        )
    )


@when("以不帶 conversation_id 的請求呼叫 agent_chat")
def call_without_conv(ctx):
    _call_chat(ctx, None)


@when(parsers.parse('以 conversation_id "{conv_id}" 的請求呼叫 agent_chat'))
def call_with_conv(ctx, conv_id):
    _call_chat(ctx, conv_id)


@then(parsers.parse("回應的 conversation_created 為 {flag}"))
def assert_created(ctx, flag):
    assert ctx["resp"].conversation_created is (flag == "true")


@then(parsers.parse('回應的 conversation_id 為 "{conv_id}"'))
def assert_conv_id(ctx, conv_id):
    assert ctx["resp"].conversation_id == conv_id


@then("回應的 structured_content.output 等於該物件")
def assert_output(ctx):
    assert ctx["resp"].structured_content.output == ctx["expected_output"]


@then("回應的 structured_content.sources 為空陣列")
def assert_sources_empty(ctx):
    assert ctx["resp"].structured_content.sources == []


@then("回應的 answer 仍為字串")
def assert_answer_str(ctx):
    assert isinstance(ctx["resp"].answer, str)


@then(parsers.parse('回應的 structured_content.contact.label 為 "{label}"'))
def assert_contact_label(ctx, label):
    assert ctx["resp"].structured_content.contact["label"] == label


@then("回應的 structured_content 為 null")
def assert_sc_null(ctx):
    assert ctx["resp"].structured_content is None


# ── SSE conversation_id 事件 ──────────────────────────────────────


@when(
    parsers.parse(
        '把請求端 conversation_id "{requested}" 套用到平台回傳 "{actual}" '
        "的 conversation_id 事件"
    )
)
def apply_event(ctx, requested, actual):
    ctx["event"] = _with_conversation_created(
        {"type": "conversation_id", "conversation_id": actual}, requested
    )


@then(parsers.parse("該事件的 conversation_created 為 {flag}"))
def assert_event_flag(ctx, flag):
    assert ctx["event"]["conversation_created"] is (flag == "true")
    assert ctx["event"]["type"] == "conversation_id"


# ── 統一錯誤處理 ─────────────────────────────────────────────────


class _Body(BaseModel):
    message: str


class _BindRequestId:
    """測試用：模擬 RequestIDMiddleware 綁定 request_id 的部分（不落 log DB）。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id="req-unit-1")

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", b"req-unit-1"))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)


@given("一個安裝了統一錯誤處理的測試應用")
def error_app(ctx):
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/missing-token")
    async def missing_token():
        raise HTTPException(status_code=401, detail="Not authenticated")

    @app.get("/snake-detail")
    async def snake():
        raise HTTPException(status_code=403, detail="insufficient_scope")

    @app.get("/api-error")
    async def api_error():
        raise ApiError(401, code="token_expired", message="Token expired")

    @app.get("/sentence-detail")
    async def sentence():
        raise HTTPException(status_code=409, detail="Version already published")

    @app.post("/validate")
    async def validate(body: _Body):
        return {"ok": True}

    app.add_middleware(_BindRequestId)
    ctx["client"] = TestClient(app, raise_server_exceptions=False)


@when(parsers.parse('對 "{path}" 送出 {method} 請求'))
def send_request(ctx, path, method):
    client = ctx["client"]
    if method == "POST":
        ctx["http"] = client.post(path, json={"message": 123})
    else:
        ctx["http"] = client.get(path)


@then(parsers.parse("狀態碼為 {status:d}"))
def assert_status(ctx, status):
    assert ctx["http"].status_code == status, ctx["http"].text


@then("錯誤 body 的 detail 是字串")
def assert_detail_str(ctx):
    assert isinstance(ctx["http"].json()["detail"], str)


@then(parsers.parse('錯誤 body 的 code 為 "{code}"'))
def assert_code(ctx, code):
    assert ctx["http"].json()["code"] == code


@then("錯誤 body 的 request_id 與回應標頭 X-Request-ID 相同")
def assert_request_id(ctx):
    body = ctx["http"].json()
    assert body["request_id"] == ctx["http"].headers["x-request-id"] == "req-unit-1"


@then(parsers.parse('錯誤 body 的 errors 是非空陣列且第一筆 loc 包含 "{field}"'))
def assert_errors(ctx, field):
    errors = ctx["http"].json()["errors"]
    assert isinstance(errors, list) and errors
    assert field in errors[0]["loc"]


# ── JWT 過期辨識 ─────────────────────────────────────────────────


@given(parsers.parse('一個以密鑰 "{secret}" 建立的 JWTService'))
def jwt_service(ctx, secret):
    ctx["secret"] = secret
    ctx["svc"] = JWTService(secret)


@when("解碼一個已過期的 access token")
def decode_expired(ctx):
    token = jwt.encode(
        {
            "sub": "u1",
            "type": "user_access",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        ctx["secret"],
        algorithm="HS256",
    )
    try:
        ctx["svc"].decode_token(token)
        ctx["exc"] = None
    except Exception as e:  # noqa: BLE001
        ctx["exc"] = e


@then("拋出 TokenExpiredError")
def assert_expired(ctx):
    assert isinstance(ctx["exc"], TokenExpiredError)
    assert isinstance(ctx["exc"], ValueError)  # 既有 except ValueError 路徑仍相容
