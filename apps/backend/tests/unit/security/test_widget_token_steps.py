"""Widget 短效票 BDD Step Definitions（Issue #67 P4）

create_app + bot repo override。
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from dependency_injector import providers
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from src.domain.bot.entity import Bot
from src.domain.bot.value_objects import BotId, BotShortCode
from src.infrastructure.auth.in_memory_token_stores import (
    InMemoryRefreshTokenStore,
    InMemoryTokenRevocationStore,
)

scenarios("unit/security/widget_token.feature")

_ORIGIN = "https://shop.example.com"


def _bot(short_code: str, origins: list[str]) -> Bot:
    return Bot(
        id=BotId(value=f"bot-{short_code}"),
        tenant_id="t1",
        name=f"bot {short_code}",
        short_code=BotShortCode(value=short_code),
        is_active=True,
        widget_enabled=True,
        widget_allowed_origins=list(origins),
        knowledge_base_ids=["kb1"],
    )


@pytest.fixture(scope="module")
def widget_app():
    mp = pytest.MonkeyPatch()
    mp.setenv("E2E_MODE", "true")
    mp.setenv("OPENAI_API_KEY", "sk-test-fake")
    from src.main import create_app

    yield create_app(skip_rate_limit=True)
    mp.undo()


@pytest.fixture
def context():
    return {}


@given("已啟動的 widget 測試應用")
def app_ready(context, widget_app):
    c = widget_app.container
    bots: dict[str, Bot] = {}
    bot_repo = AsyncMock()
    bot_repo.find_by_short_code.side_effect = lambda code: bots.get(code)

    async def _events(_cmd):
        yield {"type": "token", "content": "hi"}
        yield {"type": "done"}

    send = MagicMock()
    send.execute_stream = MagicMock(side_effect=lambda cmd: _events(cmd))
    feedback = AsyncMock()
    error_uc = AsyncMock()
    error_uc.execute.return_value = SimpleNamespace(id="e1", fingerprint="fp")
    doc_repo = AsyncMock()
    doc_repo.find_by_id.return_value = SimpleNamespace(kb_id="kb1")
    view = AsyncMock()
    view.execute.return_value = SimpleNamespace(
        content=b"pdf", content_type="application/pdf", filename="f.pdf"
    )
    overrides = {
        c.bot_repository: bot_repo,
        c.send_message_use_case: send,
        c.record_usage_use_case: AsyncMock(),
        c.submit_feedback_use_case: feedback,
        c.report_error_use_case: error_uc,
        c.document_repository: doc_repo,
        c.view_document_use_case: view,
        c.token_revocation_store: InMemoryTokenRevocationStore(),
        c.refresh_token_store: InMemoryRefreshTokenStore(),
    }
    for provider, obj in overrides.items():
        provider.override(providers.Object(obj))
    context.update(
        client=TestClient(widget_app), jwt=c.jwt_service(), bots=bots, send=send,
        overrides=overrides,
    )
    yield
    for provider in overrides:
        provider.reset_override()


@given(parsers.parse('bot "{code}" 允許的 Origin 為 "{origin}"'))
def bot_with_origin(context, code, origin):
    context["bots"][code] = _bot(code, [origin])


@given(parsers.parse('另一個 bot "{code}" 允許的 Origin 為 "{origin}"'))
def another_bot(context, code, origin):
    context["bots"][code] = _bot(code, [origin])


@given(parsers.parse('bot "{code}" 的 Origin 白名單為空'))
def bot_without_origins(context, code):
    context["bots"][code].widget_allowed_origins = []


def _config(context, origin: str | None, visitor: str | None = None):
    headers = {}
    if origin and origin != "-":
        headers["Origin"] = origin
    if visitor:
        headers["X-Visitor-Id"] = visitor
    context["resp"] = context["client"].get(
        "/api/v1/widget/ab3Kx9/config", headers=headers
    )
    if context["resp"].status_code == 200:
        body = context["resp"].json()
        context["token"] = body["widget_token"]
        context["visitor"] = body["visitor_id"]


@given("已從設定取得 visitor_id")
def config_visitor(context):
    _config(context, _ORIGIN)
    context["first_visitor"] = context["visitor"]


@given("已從設定取得 widget 票")
def config_token(context):
    _config(context, _ORIGIN)


@when(parsers.parse('以 Origin "{origin}" 取得 widget 設定'))
def get_config(context, origin):
    _config(context, origin)


@when("以該 visitor_id 再取得一次 widget 設定")
def get_config_same_visitor(context):
    _config(context, _ORIGIN, visitor=context["first_visitor"])


@when(parsers.parse('以偽造的 visitor_id "{visitor}" 取得 widget 設定'))
def get_config_forged_visitor(context, visitor):
    _config(context, _ORIGIN, visitor=visitor)


_BODIES = {
    "chat/stream": {"message": "hi"},
    "feedback": {"conversation_id": "c1", "message_id": "m1", "rating": "thumbs_up"},
    "error": {"error_type": "E", "message": "boom"},
}


@when(parsers.parse('無票請求 widget "{method}" "{path}"'))
def request_without_token(context, method, path):
    body = None
    for key, value in _BODIES.items():
        if path.endswith(key):
            body = value
    context["resp"] = context["client"].request(
        method, path, json=body, headers={"Origin": _ORIGIN}
    )


def _chat(context, code: str, origin: str, extra: dict | None = None, token=None):
    headers = {"Authorization": f"Bearer {token or context['token']}", "Origin": origin}
    headers.update(extra or {})
    context["resp"] = context["client"].post(
        f"/api/v1/widget/{code}/chat/stream", json={"message": "hi"}, headers=headers
    )


@when(parsers.parse(
    '持票以 Origin "{origin}" 與 header X-Visitor-Id "{visitor}" 送出聊天'
))
def chat_with_spoofed_visitor(context, origin, visitor):
    _chat(context, "ab3Kx9", origin, {"X-Visitor-Id": visitor})


@when(parsers.re(r'持票以 Origin "(?P<origin>[^"]+)" 送出聊天$'))
def chat_with_origin(context, origin):
    _chat(context, "ab3Kx9", origin)


@when(parsers.parse('持票對 bot "{code}" 送出聊天'))
def chat_other_bot(context, code):
    _chat(context, code, _ORIGIN)


@when("以租戶使用者的 access 票送出聊天")
def chat_with_user_token(context):
    token = context["jwt"].create_user_token("u1", "t1", "user")
    _chat(context, "ab3Kx9", _ORIGIN, token=token)


@when(parsers.parse('以 query 參數帶票請求文件 "{doc_id}" 檢視'))
def view_document(context, doc_id):
    context["resp"] = context["client"].get(
        f"/api/v1/widget/ab3Kx9/documents/{doc_id}/view",
        params={"wt": context["token"]},
    )


@when(parsers.parse('持票以 Origin "{origin}" 送出回饋'))
def feedback_with_token(context, origin):
    context["resp"] = context["client"].post(
        "/api/v1/widget/ab3Kx9/feedback",
        json=_BODIES["feedback"],
        headers={"Authorization": f"Bearer {context['token']}", "Origin": origin},
    )


@then(parsers.parse("widget 回應狀態碼為 {status:d}"))
def status_is(context, status):
    assert context["resp"].status_code == status, context["resp"].text


@then(parsers.parse(
    "設定回應含 widget_token（type widget_access、綁 bot 與 Origin）"
    "與 expires_in {exp:d}"
))
def config_has_token(context, exp):
    body = context["resp"].json()
    payload = context["jwt"].decode_token(body["widget_token"])
    assert payload["type"] == "widget_access"
    assert payload["sub"] == "bot-ab3Kx9"
    assert payload["origin"] == _ORIGIN
    assert payload["tenant_id"] == "t1"
    assert body["token_expires_in"] == exp


@then("設定回應的 visitor_id 帶有效簽章")
def visitor_signed(context):
    signer = context["client"].app.container.visitor_id_signer()
    assert signer.verify(context["visitor"]) is not None


@then("設定回應的 visitor_id 與先前相同")
def visitor_same(context):
    assert context["visitor"] == context["first_visitor"]


@then("設定回應的 visitor_id 與先前不同")
def visitor_differs(context):
    assert context["visitor"] != context["first_visitor"]
    assert "someone-else" not in context["visitor"]


@then(parsers.parse(
    '聊天命令的 visitor_id 等於票內 visitor_id 且 identity_source 為 "{source}"'
))
def command_visitor(context, source):
    payload = context["jwt"].decode_token(context["token"])
    cmd = context["send"].execute_stream.call_args.args[0]
    assert cmd.visitor_id == payload["visitor_id"]
    assert cmd.visitor_id != "spoofed"
    assert cmd.identity_source == source
