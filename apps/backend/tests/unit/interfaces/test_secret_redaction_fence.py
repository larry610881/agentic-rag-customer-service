"""Fence（Issue #101）：憑證不得以明文出現在 API 回應。

保護對象：LINE channel secret / access token、MCP 綁定的 env 值、供應商 API key、
api-key 的 secret（雜湊與 salt）、通知管道設定（含 webhook URL 的 token）、使用者
密碼雜湊、widget 身分 secret，以及任何進入設定快照 / 稽核視圖的密鑰鍵。

三層檢查：

1. 結構：列舉 app 所有 route 可達的 pydantic 回應模型，欄位名像密鑰的（secret /
   token / api_key / password / credential / webhook / env…，數值與布林型別除外）
   必須在 MASKED_FIELDS（下方行為測試驗證為遮罩）或 INTENTIONAL_FIELDS（設計上就
   要回傳，附理由，例如登入票、建立時只回一次的 client_secret）。
2. 結構：回應不是 pydantic 模型（直接回 dict）的 handler，掃描它（與它呼叫的同模組
   helper）的 dict 字面鍵，同樣分類。
3. 行為：把帶「真實密鑰值」的 domain 物件丟進實際的回應組裝函式，序列化後整段
   搜尋，密鑰值一個字元都不能出現。

新增回應欄位或回應組裝函式碰到密鑰時，這裡會紅，逼你做決定並留下理由。
"""

from __future__ import annotations

import ast
import inspect
import json
import re
import sys
import textwrap
import typing
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.routing import APIRoute
from pydantic import BaseModel

SECRET_NAME = re.compile(
    r"secret|token|api_?key|password|passwd|credential|webhook|private_key"
    r"|signing_key|authorization|(^|_)env(_|$)",
    re.IGNORECASE,
)
# 旗標 / 計數型鍵名只說「有沒有」，不帶值
NON_VALUE_NAME = re.compile(r"^(has|is)_|_(count|expires_in)$")
_TOKEN_COUNTERS = re.compile(r"(^|_)tokens(_|$)")  # input_tokens 等用量計數

# (Model, field)：回應組裝函式把原值換成 "***"（由 test_bot_response_masks_*
# 以真實密鑰驗證）
MASKED_FIELDS = {
    ("BotResponse", "line_channel_secret"),
    ("BotResponse", "line_channel_access_token"),
}

_LOGIN = "登入 / 換票本身就是要把票交給呼叫者"
_WIDGET = "widget 短效票（綁 bot + origin），前端必須拿到才能呼叫"
INTENTIONAL_FIELDS: dict[tuple[str, str], str] = {
    ("TokenResponse", "access_token"): _LOGIN,
    ("TokenResponse", "refresh_token"): _LOGIN,
    ("TokenResponse", "token_type"): "固定字串 bearer",
    ("ClientCredentialsResponse", "access_token"): _LOGIN,
    ("ClientCredentialsResponse", "token_type"): "固定字串 bearer",
    ("ApiKeyCreatedResponse", "client_secret"): (
        "只在建立回應出現一次；DB 只存 salt+hash，之後的列表 / 查詢不再回傳"
    ),
    ("ApiKeyCreatedResponse", "secret_prefix"): "secret 的前幾碼，供辨識用，不足以驗證",
    ("ApiKeyResponse", "secret_prefix"): "secret 的前幾碼，供辨識用，不足以驗證",
    ("WidgetConfigResponse", "widget_token"): _WIDGET,
    ("WidgetIdentifyResponse", "widget_token"): _WIDGET,
    ("DryRunRecalculateResponse", "dry_run_token"): (
        "重算的確認碼（綁 dry-run 參數），不是憑證；僅 system_admin"
    ),
    ("McpServerResponse", "required_env"): (
        "只有環境變數「名稱」，值存在 bot 綁定且遮罩"
    ),
}

# (module 名, dict 鍵)：沒有 response_model 的 handler 直接回 dict 時出現的鍵
INTENTIONAL_DICT_KEYS: dict[tuple[str, str], str] = {
    ("widget_identity_router", "secret"): (
        "POST /secret/rotate 只在輪替當下回傳一次，之後 GET 只回 has_secret"
    ),
}


@pytest.fixture(scope="module")
def app():
    mp = pytest.MonkeyPatch()
    mp.setenv("E2E_MODE", "true")
    mp.setenv("OPENAI_API_KEY", "sk-test-fake")
    from src.main import create_app

    yield create_app(skip_rate_limit=True)
    mp.undo()


def _iter_api_routes(routes):
    for r in routes:
        if isinstance(r, APIRoute):
            yield r
        elif hasattr(r, "original_router"):  # FastAPI _IncludedRouter
            yield from _iter_api_routes(r.original_router.routes)
        elif hasattr(r, "routes"):
            yield from _iter_api_routes(r.routes)


def _is_secret_name(name: str) -> bool:
    if _TOKEN_COUNTERS.search(name) or NON_VALUE_NAME.search(name):
        return False
    return bool(SECRET_NAME.search(name))


_SCALAR_NON_TEXT = (int, float, bool, datetime)


def _holds_text(annotation) -> bool:
    """數值 / 布林 / 時間欄位裝不下憑證；其餘（str、dict、list…）都算。"""
    args = [a for a in typing.get_args(annotation) if a is not type(None)]
    if args and typing.get_origin(annotation) in (typing.Union, type(int | None)):
        return any(_holds_text(a) for a in args)
    return not (
        isinstance(annotation, type) and issubclass(annotation, _SCALAR_NON_TEXT)
    )


def _collect_models(tp, acc: set[type[BaseModel]]) -> set[type[BaseModel]]:
    if isinstance(tp, type) and issubclass(tp, BaseModel):
        if tp in acc:
            return acc
        acc.add(tp)
        for f in tp.model_fields.values():
            _collect_models(f.annotation, acc)
    for a in typing.get_args(tp):
        _collect_models(a, acc)
    return acc


def _secret_model_fields(app) -> set[tuple[str, str]]:
    models: set[type[BaseModel]] = set()
    for route in _iter_api_routes(app.routes):
        if route.response_model is not None:
            _collect_models(route.response_model, models)
    return {
        (m.__name__, name)
        for m in models
        for name, f in m.model_fields.items()
        if _is_secret_name(name) and _holds_text(f.annotation)
    }


def _dict_keys(fn, seen: set) -> set[str]:
    """handler 與它呼叫的同模組函式裡，dict 字面鍵（字串常數）。"""
    fn = inspect.unwrap(fn)
    if fn in seen:
        return set()
    seen.add(fn)
    try:
        tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    except (OSError, TypeError):
        return set()
    mod = sys.modules[fn.__module__]
    keys: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Dict):
            keys |= {
                k.value
                for k in n.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)
            }
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
            target = getattr(mod, n.func.id, None)
            if inspect.isfunction(target) and target.__module__ == mod.__name__:
                keys |= _dict_keys(target, seen)
    return keys


def _secret_dict_keys(app) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for route in _iter_api_routes(app.routes):
        if _collect_models(route.response_model, set()):
            continue  # 有 pydantic 回應模型的由欄位檢查負責
        module = route.endpoint.__module__.rsplit(".", 1)[-1]
        for key in _dict_keys(route.endpoint, set()):
            if _is_secret_name(key):
                out.add((module, key))
    return out


# ---------------------------------------------------------------------------
# 1–2. 結構：每個像密鑰的回應欄位都被分類
# ---------------------------------------------------------------------------


def test_every_secret_like_response_field_is_masked_or_intentional(app):
    found = _secret_model_fields(app)
    unclassified = sorted(found - MASKED_FIELDS - set(INTENTIONAL_FIELDS))
    assert unclassified == [], (
        "response fields that look like credentials must be masked (and added "
        f"to MASKED_FIELDS with a behaviour test) or justified: {unclassified}"
    )


def test_secret_field_lists_are_honest(app):
    found = _secret_model_fields(app)
    stale = sorted((MASKED_FIELDS | set(INTENTIONAL_FIELDS)) - found)
    assert stale == [], f"entries no longer present in any response: {stale}"
    assert not MASKED_FIELDS & set(INTENTIONAL_FIELDS)


def test_every_secret_like_dict_key_is_intentional(app):
    found = _secret_dict_keys(app)
    unclassified = sorted(found - set(INTENTIONAL_DICT_KEYS))
    assert unclassified == [], (
        f"dict responses with credential-like keys must be justified: {unclassified}"
    )
    stale = sorted(set(INTENTIONAL_DICT_KEYS) - found)
    assert stale == [], f"INTENTIONAL_DICT_KEYS entries no longer present: {stale}"


def test_scan_reaches_the_response_surface(app):
    models: set[type[BaseModel]] = set()
    for route in _iter_api_routes(app.routes):
        if route.response_model is not None:
            _collect_models(route.response_model, models)
    names = {m.__name__ for m in models}
    assert len(models) > 100, "route scan lost the included routers"
    assert {"BotResponse", "ProviderSettingResponse", "ApiKeyResponse"} <= names


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("line_channel_secret", True),
        ("api_key", True),
        ("env_values", True),
        ("required_env", True),
        ("webhook_url", True),
        ("has_api_key", False),
        ("input_tokens", False),
        ("max_tokens", False),
        ("token_expires_in", False),
        ("environment", False),
        ("output_keywords", False),
    ],
)
def test_secret_name_pattern(name, expected):
    assert _is_secret_name(name) is expected


# ---------------------------------------------------------------------------
# 3. 行為：真實密鑰值丟進回應組裝函式，序列化後不得出現
# ---------------------------------------------------------------------------

LINE_SECRET = "line-secret-6f1c0a9e"
LINE_TOKEN = "line-access-token-b27d44"
MCP_ENV = "mcp-env-value-9a8b7c"
PROVIDER_KEY = "sk-live-provider-3141592653"
KEY_HASH = "api-key-hash-2718281828"
KEY_SALT = "api-key-salt-1618033988"
WEBHOOK = "https://example.webhook.office.com/webhookb2/tok-5772156649"
PASSWORD_HASH = "$2b$12$passwordhashvalue0000000000"
IDENTITY_SECRET = "identity-secret-1414213562"


def _dump(obj) -> str:
    if isinstance(obj, BaseModel):
        return obj.model_dump_json()
    return json.dumps(obj, default=str, ensure_ascii=False)


def _assert_absent(payload: str, *secrets: str) -> None:
    leaked = [s for s in secrets if s in payload]
    assert leaked == [], f"credential leaked into response: {leaked}"


def _bot_with_secrets():
    from src.domain.bot.entity import Bot, BotMcpBinding

    return Bot(
        tenant_id="t1",
        name="bot",
        line_channel_secret=LINE_SECRET,
        line_channel_access_token=LINE_TOKEN,
        mcp_bindings=[
            BotMcpBinding(
                registry_id="reg-1",
                enabled_tools=["search"],
                env_values={"API_KEY": MCP_ENV},
            )
        ],
    )


def test_bot_response_masks_line_credentials_and_mcp_env():
    from src.interfaces.api.bot_router import _to_response

    resp = _to_response(_bot_with_secrets())
    _assert_absent(_dump(resp), LINE_SECRET, LINE_TOKEN, MCP_ENV)
    assert resp.line_channel_secret == "***"
    assert resp.line_channel_access_token == "***"
    assert resp.mcp_bindings[0]["env_values"] == {"API_KEY": "***"}


def test_bot_response_without_line_credentials_returns_null():
    from src.domain.bot.entity import Bot
    from src.interfaces.api.bot_router import _to_response

    resp = _to_response(Bot(tenant_id="t1", name="bot"))
    assert resp.line_channel_secret is None
    assert resp.line_channel_access_token is None


def test_bot_audit_view_and_version_snapshot_strip_credentials():
    """稽核紀錄（/bots/{id}/audit-logs）與設定版本快照都是 API 可讀的。"""
    from src.application.bot.update_bot_use_case import UpdateBotUseCase
    from src.domain.prompt_gate.config_snapshot import take_snapshot

    bot = _bot_with_secrets()
    _assert_absent(
        _dump(UpdateBotUseCase._audit_view(bot)), LINE_SECRET, LINE_TOKEN, MCP_ENV
    )
    _assert_absent(_dump(take_snapshot(bot)), LINE_SECRET, LINE_TOKEN, MCP_ENV)


def test_effective_config_snapshot_scrubs_secret_keys():
    """/config-snapshots/{hash} 回傳的有效設定快照。"""
    from src.domain.observability.effective_config import EffectiveConfig

    cfg = EffectiveConfig(
        channel="web",
        bot_id="b1",
        system_prompt="hi",
        llm_params={"api_key": PROVIDER_KEY},
        extra={
            "mcp": {"env_values": {"K": MCP_ENV}},
            "line": {"channel_secret": LINE_SECRET, "access_token": LINE_TOKEN},
            "headers": {"Authorization": f"Bearer {PROVIDER_KEY}"},
        },
    )
    _assert_absent(
        _dump(cfg.to_snapshot()), PROVIDER_KEY, MCP_ENV, LINE_SECRET, LINE_TOKEN
    )


def test_provider_setting_response_never_returns_api_key():
    from src.domain.platform.entity import ProviderSetting
    from src.interfaces.api.provider_setting_router import _to_response

    resp = _to_response(ProviderSetting(api_key_encrypted=PROVIDER_KEY))
    _assert_absent(_dump(resp), PROVIDER_KEY)
    assert resp.has_api_key is True


def test_api_key_listing_never_returns_secret_material():
    from src.domain.auth.api_key import ApiKey
    from src.interfaces.api.api_key_router import _to_response

    key = ApiKey(
        tenant_id="t1",
        name="ci",
        secret_hash=KEY_HASH,
        secret_salt=KEY_SALT,
        secret_prefix="ak_1234",
    )
    _assert_absent(_dump(_to_response(key)), KEY_HASH, KEY_SALT)
    # 建立 / 撤銷的稽核列（/audit-logs 可讀）
    from src.application.auth.api_key_use_cases import _audit_view

    _assert_absent(_dump(_audit_view(key)), KEY_HASH, KEY_SALT)


def test_notification_channel_response_omits_config():
    """config（含 Teams / Slack webhook URL 的 token、SMTP 密碼）不得回傳。"""
    from src.domain.observability.notification import NotificationChannel
    from src.interfaces.api.notification_router import _channel_to_dict

    for config in (json.dumps({"webhook_url": WEBHOOK}), "gAAAAA-encrypted-blob"):
        ch = NotificationChannel(
            id="c1", channel_type="teams", name="ops", config_encrypted=config
        )
        payload = _dump(_channel_to_dict(ch))
        _assert_absent(payload, WEBHOOK, "gAAAAA-encrypted-blob")
        assert "config" not in _channel_to_dict(ch)


def test_user_responses_never_return_password_hash():
    from src.domain.auth.entity import User
    from src.domain.auth.value_objects import Role
    from src.interfaces.api.admin_router import _user_response

    user = User(tenant_id="t1", hashed_password=PASSWORD_HASH, role=Role.USER)
    _assert_absent(_dump(_user_response(user)), PASSWORD_HASH)


def test_widget_identity_status_never_returns_secret():
    from src.interfaces.api.widget_identity_router import _status_dict

    status = SimpleNamespace(
        tenant_id="t1",
        has_secret=True,
        is_enabled=True,
        enforce_verified=False,
        rotated_at=datetime.now(timezone.utc),
        secret=IDENTITY_SECRET,
        secret_encrypted=IDENTITY_SECRET,
    )
    _assert_absent(_dump(_status_dict(status)), IDENTITY_SECRET)
