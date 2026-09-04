"""Widget 身分階梯 BDD Step Definitions（Issue #68 P7b）"""

import asyncio
import hashlib
import hmac
import json
import time
from base64 import b64encode
from unittest.mock import AsyncMock, MagicMock

import pytest
from dependency_injector import providers
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.abuse.abuse_control_service import AbuseControlService
from src.application.line.handle_webhook_use_case import HandleWebhookUseCase
from src.application.widget.identity_use_cases import VerifyWidgetIdentityUseCase
from src.domain.abuse.policy import AbusePolicy, AbuseSubject, SubjectKind
from src.domain.agent.entity import AgentResponse
from src.domain.bot.entity import Bot
from src.domain.bot.value_objects import BotId, BotShortCode
from src.domain.widget.identity import (
    TenantIdentitySecret,
    compute_identity_hash,
    verify_identity,
)
from src.infrastructure.abuse.in_memory_abuse_score_store import (
    InMemoryAbuseScoreStore,
)
from src.infrastructure.auth.in_memory_token_stores import (
    InMemoryRefreshTokenStore,
    InMemoryTokenRevocationStore,
)
from src.interfaces.api.rate_limit_middleware import _resolve_endpoint_group

scenarios("unit/abuse/widget_identity.feature")

_T = "t1"
_ORIGIN = "https://shop.example.com"
_CHANNEL_SECRET = "line-secret"


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _PlainEnc:
    def encrypt(self, s: str) -> str:
        return "enc:" + s

    def decrypt(self, s: str) -> str:
        return s[4:]


@pytest.fixture
def ctx():
    return {}


# ---------------------------------------------------------------------------
# domain
# ---------------------------------------------------------------------------


@given(parsers.parse('租戶 identity secret "{secret}"'))
def secret(ctx, secret):
    ctx["secret"] = secret


@when(parsers.parse('宿主為使用者 "{uid}" 產生 {minutes:d} 分鐘後到期的簽章'))
def sign(ctx, uid, minutes):
    exp = int(time.time()) + minutes * 60
    ctx["claim"] = (uid, exp, compute_identity_hash(ctx["secret"], uid, exp))


@when(parsers.parse(
    '宿主為使用者 "{uid}" 產生 {offset:d} 秒後到期的簽章，並以 "{tamper}" 竄改'
))
def sign_tampered(ctx, uid, offset, tamper):
    exp = int(time.time()) + offset
    h = compute_identity_hash(ctx["secret"], uid, exp)
    if tamper == "hash":
        h = "0" * 64
    if tamper == "user_id":
        uid = "someone-else"
    ctx["claim"] = (uid, exp, h)


@then(parsers.parse("驗證結果為{outcome}"))
def verify_outcome(ctx, outcome):
    uid, exp, h = ctx["claim"]
    assert verify_identity(ctx["secret"], uid, exp, h) is (outcome == "通過")


# ---------------------------------------------------------------------------
# use case
# ---------------------------------------------------------------------------


def _repo_with(secret_plain: str | None, enforce: bool):
    repo = AsyncMock()
    if secret_plain is None:
        repo.get.return_value = None
    else:
        repo.get.return_value = TenantIdentitySecret(
            tenant_id=_T, secret_encrypted="enc:" + secret_plain,
            enforce_verified=enforce,
        )
    return repo


def _uc(ctx, secret_plain: str | None, enforce: bool):
    ctx["store"] = InMemoryAbuseScoreStore()
    ctx["abuse"] = AbuseControlService(ctx["store"], AbusePolicy())
    ctx["plain_secret"] = secret_plain or "none"
    ctx["uc"] = VerifyWidgetIdentityUseCase(
        _repo_with(secret_plain, enforce), _PlainEnc(), abuse_control=ctx["abuse"]
    )


@given(parsers.parse("租戶 \"{tid}\" 已設定 identity secret，強制驗證 {state}"))
def tenant_secret(ctx, tid, state):
    _uc(ctx, "s3cr3t", state == "開啟")


@given(parsers.parse('租戶 "{tid}" 未設定 identity secret'))
def tenant_no_secret(ctx, tid):
    _uc(ctx, None, False)


def _identify(ctx, vid: str, correct: bool):
    exp = int(time.time()) + 600
    h = compute_identity_hash(ctx["plain_secret"], "member-42", exp)
    if not correct:
        h = "f" * 64
    ctx["verdict"] = _run(ctx["uc"].execute(
        tenant_id=_T, visitor_id=vid, user_id="member-42", exp=exp, presented_hash=h,
    ))


@when(parsers.parse('訪客 "{vid}" 送出正確的 identify'))
def identify_ok(ctx, vid):
    _identify(ctx, vid, True)


@when(parsers.parse('訪客 "{vid}" 送出錯誤的 identify'))
def identify_bad(ctx, vid):
    _identify(ctx, vid, False)


@then(parsers.parse("identify 結果 verified 為 {value}"))
def verdict_verified(ctx, value):
    assert ctx["verdict"].verified is (value == "true")


@then(parsers.parse("identify 結果 verified 為 {v} 且 enforce 為 {e}"))
def verdict_enforce(ctx, v, e):
    assert ctx["verdict"].verified is (v == "true")
    assert ctx["verdict"].enforce is (e == "true")


@then(parsers.parse('identify 結果 reason 為 "{reason}"'))
def verdict_reason(ctx, reason):
    assert ctx["verdict"].reason == reason


def _visitor_score(ctx, vid):
    key = AbuseSubject(SubjectKind.VISITOR, vid).key(_T)
    return _run(ctx["store"].get_score(key, 1.0))


@then(parsers.parse('訪客 "{vid}" 被記了 identify_fail'))
def recorded_fail(ctx, vid):
    assert abs(_visitor_score(ctx, vid) - 2.0) < 0.5


@then(parsers.parse('訪客 "{vid}" 沒有被記 identify_fail'))
def not_recorded(ctx, vid):
    assert _visitor_score(ctx, vid) == 0.0


# ---------------------------------------------------------------------------
# endpoint
# ---------------------------------------------------------------------------


def _bot() -> Bot:
    return Bot(
        id=BotId(value="bot-ab3Kx9"), tenant_id=_T, name="b",
        short_code=BotShortCode(value="ab3Kx9"), is_active=True, widget_enabled=True,
        widget_allowed_origins=[_ORIGIN],
    )


@pytest.fixture(scope="module")
def identify_app():
    mp = pytest.MonkeyPatch()
    mp.setenv("E2E_MODE", "true")
    mp.setenv("OPENAI_API_KEY", "sk-test-fake")
    from src.main import create_app

    yield create_app(skip_rate_limit=True)
    mp.undo()


@given(parsers.parse('已啟動的 identify 測試應用，租戶 "{tid}" 強制驗證 {state}'))
def app_ready(ctx, identify_app, tid, state):
    c = identify_app.container
    bot_repo = AsyncMock()
    bot_repo.find_by_short_code.return_value = _bot()
    store = InMemoryAbuseScoreStore()
    abuse = AbuseControlService(store, AbusePolicy())
    ctx["plain_secret"] = "s3cr3t"
    verify_uc = VerifyWidgetIdentityUseCase(
        _repo_with("s3cr3t", state == "開啟"), _PlainEnc(), abuse_control=abuse
    )
    overrides = {
        c.bot_repository: bot_repo,
        c.abuse_control_service: abuse,
        c.verify_widget_identity_use_case: verify_uc,
        c.token_revocation_store: InMemoryTokenRevocationStore(),
        c.refresh_token_store: InMemoryRefreshTokenStore(),
    }
    for prov, obj in overrides.items():
        prov.override(providers.Object(obj))
    ctx.update(
        client=TestClient(identify_app), jwt=c.jwt_service(), overrides=overrides
    )
    yield
    for prov in overrides:
        prov.reset_override()


@given(parsers.parse('持有 bot "{code}" 的 widget 票'))
def widget_token(ctx, code):
    token, _ = ctx["jwt"].create_widget_token(
        bot_id=f"bot-{code}", tenant_id=_T, origin=_ORIGIN, visitor_id="v-1"
    )
    ctx["token"] = token


def _post_identify(ctx, uid: str, correct: bool, with_token: bool = True):
    exp = int(time.time()) + 600
    h = compute_identity_hash(ctx["plain_secret"], uid, exp) if correct else "f" * 64
    headers = {"Origin": _ORIGIN}
    if with_token:
        headers["Authorization"] = f"Bearer {ctx['token']}"
    ctx["resp"] = ctx["client"].post(
        "/api/v1/widget/ab3Kx9/identify",
        json={"user_id": uid, "exp": exp, "hash": h}, headers=headers,
    )


@when(parsers.parse('持票送出正確的 identify "{uid}"'))
def post_ok(ctx, uid):
    _post_identify(ctx, uid, True)


@when(parsers.parse('持票送出錯誤的 identify "{uid}"'))
def post_bad(ctx, uid):
    _post_identify(ctx, uid, False)


@when(parsers.parse('無票送出 identify "{uid}"'))
def post_no_token(ctx, uid):
    _post_identify(ctx, uid, True, with_token=False)


@then(parsers.parse("identify 端點回應 {status:d} 且 identified 為 {value}"))
def endpoint_identified(ctx, status, value):
    assert ctx["resp"].status_code == status, ctx["resp"].text
    assert ctx["resp"].json()["identified"] is (value == "true")


@then(parsers.parse("identify 端點回應 {status:d}"))
def endpoint_status(ctx, status):
    assert ctx["resp"].status_code == status, ctx["resp"].text


@then(parsers.parse('新票的 end_user_id 為 "{uid}"'))
def new_token_end_user(ctx, uid):
    payload = ctx["jwt"].decode_token(ctx["resp"].json()["widget_token"])
    assert payload["end_user_id"] == uid and payload["type"] == "widget_access"


# ---------------------------------------------------------------------------
# rate group
# ---------------------------------------------------------------------------


@when(parsers.parse('解析路徑 "{path}" 的限流群組'))
def resolve_group(ctx, path):
    ctx["group"] = _resolve_endpoint_group(path)


@then(parsers.parse('限流群組為 "{group}"'))
def group_is(ctx, group):
    assert ctx["group"] == group


# ---------------------------------------------------------------------------
# LINE group
# ---------------------------------------------------------------------------


def _line_bot() -> Bot:
    return Bot(
        tenant_id=_T, name="測試bot", short_code="test01",
        line_channel_secret=_CHANNEL_SECRET, line_channel_access_token="token",
        knowledge_base_ids=["kb1"],
    )


def _signed_group_body(user_id: str, group_id: str) -> tuple[str, str]:
    body = json.dumps({
        "events": [{
            "type": "message", "replyToken": "rt-1", "timestamp": 1750000000000,
            "source": {"type": "group", "groupId": group_id, "userId": user_id},
            "message": {"type": "text", "text": "hello"},
        }]
    })
    sig = b64encode(
        hmac.new(_CHANNEL_SECRET.encode(), body.encode(), hashlib.sha256).digest()
    ).decode()
    return body, sig


@given(parsers.parse("接了異常控管的 LINE 群組 webhook use case，群組每分鐘上限 {n:d}"))
def line_group_uc(ctx, n):
    agent = AsyncMock()
    agent.process_message.return_value = AgentResponse(answer="正常回覆")
    line_service = AsyncMock()
    line_service.verify_signature = AsyncMock(return_value=True)
    factory = MagicMock()
    factory.create.return_value = line_service
    bot_repo = AsyncMock()
    bot_repo.find_by_short_code.return_value = _line_bot()
    ctx["store"] = InMemoryAbuseScoreStore()
    policy = AbusePolicy(line_group_max_per_minute=n)
    ctx["abuse"] = AbuseControlService(ctx["store"], policy)
    ctx["line_uc"] = HandleWebhookUseCase(
        agent_service=agent, bot_repository=bot_repo, line_service_factory=factory,
        abuse_control=ctx["abuse"],
    )
    ctx["line_service"] = line_service


@given(parsers.parse('LINE 使用者 "{uid}" 已被鎖定在等級 {level:d}'))
def line_locked(ctx, uid, level):
    _run(ctx["store"].set_level(
        AbuseSubject(SubjectKind.LINE_USER, uid).key(_T), level, 600
    ))


@when(parsers.parse('群組 "{gid}" 的使用者 "{uid}" 連續送出 {n:d} 則訊息'))
def group_messages(ctx, gid, uid, n):
    for _ in range(n):
        body, sig = _signed_group_body(uid, gid)
        _run(ctx["line_uc"].execute_for_bot("test01", body, sig))


def _line_score(ctx, uid):
    return _run(ctx["store"].get_score(
        AbuseSubject(SubjectKind.LINE_USER, uid).key(_T), 1.0
    ))


@then(parsers.parse('LINE 使用者 "{uid}" 的異常分數為 {value:g}'))
def line_score(ctx, uid, value):
    assert abs(_line_score(ctx, uid) - value) < 0.5, _line_score(ctx, uid)


@then(parsers.parse('群組 "{gid}" 的使用者 "{uid}" 送出 1 則訊息後分數為 {value:g}'))
def other_user_score(ctx, gid, uid, value):
    body, sig = _signed_group_body(uid, gid)
    _run(ctx["line_uc"].execute_for_bot("test01", body, sig))
    assert abs(_line_score(ctx, uid) - value) < 0.5


@then("LINE 沒有回覆任何訊息")
def line_silent(ctx):
    ctx["line_service"].reply_text.assert_not_awaited()
    ctx["line_service"].reply_with_quick_reply.assert_not_awaited()
