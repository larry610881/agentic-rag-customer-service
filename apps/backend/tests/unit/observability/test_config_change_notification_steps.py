"""BDD steps — 設定變更通知（Issue #77）"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.audit.audit_recorder import AuditRecorder
from src.application.observability.config_change_notification_use_case import (
    DispatchConfigChangeNotificationUseCase,
)
from src.application.observability.notification_use_cases import (
    NotificationDispatcher,
)
from src.application.tenant.notification_preferences_use_cases import (
    GetTenantNotificationPreferencesUseCase,
    UpdateTenantNotificationPreferencesUseCase,
)
from src.domain.audit.entity import SOURCE_API, AuditEntry
from src.domain.auth.entity import User
from src.domain.auth.repository import UserRepository
from src.domain.auth.value_objects import Email, Role, UserId
from src.domain.bot.entity import Bot
from src.domain.bot.repository import BotRepository
from src.domain.bot.value_objects import BotId
from src.domain.bot.worker_config import WorkerConfig
from src.domain.bot.worker_repository import WorkerConfigRepository
from src.domain.observability.config_change import (
    DEFAULT_NOTIFY_GROUPS,
    groups_touched,
)
from src.domain.observability.notification import (
    NotificationChannel,
    NotificationChannelRepository,
    NotificationSender,
)
from src.domain.shared.exceptions import ValidationError
from src.domain.tenant.entity import Tenant
from src.domain.tenant.repository import TenantRepository
from src.domain.tenant.value_objects import TenantId

scenarios("unit/observability/config_change_notification.feature")

_NOW = datetime(2026, 9, 7, 10, 0, tzinfo=timezone.utc)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class _RecordingSender(NotificationSender):
    def __init__(self, sink: list) -> None:
        self._sink = sink

    async def send(self, channel, subject, body) -> None:
        self._sink.append((channel.name, subject, body))

    def channel_type(self) -> str:
        return "teams"


@pytest.fixture
def context():
    tenants: dict[str, Tenant] = {}
    tenant_repo = AsyncMock(spec=TenantRepository)
    tenant_repo.find_by_id = AsyncMock(side_effect=lambda tid: tenants.get(tid))
    tenant_repo.save = AsyncMock(
        side_effect=lambda t: tenants.__setitem__(t.id.value, t)
    )
    users: dict[str, User] = {}
    user_repo = AsyncMock(spec=UserRepository)
    user_repo.find_by_id = AsyncMock(side_effect=lambda uid: users.get(uid))
    channel_repo = AsyncMock(spec=NotificationChannelRepository)
    channels: list[NotificationChannel] = []
    channel_repo.list_enabled = AsyncMock(side_effect=lambda: list(channels))
    bot_repo = AsyncMock(spec=BotRepository)
    bots: dict[str, Bot] = {}
    bot_repo.find_by_id = AsyncMock(side_effect=lambda bid: bots.get(bid))
    worker_repo = AsyncMock(spec=WorkerConfigRepository)
    workers: dict[str, WorkerConfig] = {}
    worker_repo.find_by_id = AsyncMock(side_effect=lambda wid: workers.get(wid))
    audit_repo = AsyncMock()
    audit_repo.append = AsyncMock()
    sent: list = []
    return {
        "tenants": tenants, "tenant_repo": tenant_repo,
        "users": users, "user_repo": user_repo,
        "channels": channels, "channel_repo": channel_repo,
        "bots": bots, "bot_repo": bot_repo,
        "workers": workers, "worker_repo": worker_repo,
        "audit_repo": audit_repo,
        "sent": sent,
        "dispatcher": NotificationDispatcher(senders={"teams": _RecordingSender(sent)}),
        "entry": None,
        "error": None,
    }


# ── Background / Given ──


@given(parsers.parse('租戶 "{tenant_id}" 名稱為 "{name}"'))
def setup_tenant(context, tenant_id, name):
    context["tenants"][tenant_id] = Tenant(id=TenantId(value=tenant_id), name=name)


@given(parsers.parse('使用者 "{user_id}" 的 email 為 "{email}"，角色 "{role}"'))
def setup_user(context, user_id, email, role):
    context["users"][user_id] = User(
        id=UserId(user_id), tenant_id="t-001", email=Email(email), role=Role(role),
    )


@given(parsers.parse('租戶 "{tenant_id}" 未設定通知群組（採平台預設）'))
def tenant_default_groups(context, tenant_id):
    context["tenants"][tenant_id].config_change_notify_fields = None


@given(parsers.re(r'租戶 "(?P<tenant_id>[^"]+)" 設定通知群組為 "(?P<groups>[^"]*)"$'))
def tenant_groups(context, tenant_id, groups):
    context["tenants"][tenant_id].config_change_notify_fields = (
        [g for g in groups.split(",") if g]
    )


def _channel(name: str, notify_config_change: bool) -> NotificationChannel:
    return NotificationChannel(
        id=f"ch-{name}", channel_type="teams", name=name, enabled=True,
        config_encrypted="{}", notify_config_change=notify_config_change,
    )


@given(parsers.parse('有一個已啟用且勾選設定變更的通知渠道 "{name}"'))
def channel_on(context, name):
    context["channels"].append(_channel(name, True))


@given(parsers.parse('有一個已啟用但未勾選設定變更的通知渠道 "{name}"'))
def channel_off(context, name):
    context["channels"].append(_channel(name, False))


def _entry(**kw) -> AuditEntry:
    base: dict = {
        "action": "update", "actor_user_id": "u-001", "tenant_id": "t-001",
        "source": SOURCE_API, "created_at": _NOW,
    }
    base.update(kw)
    return AuditEntry(**base)


@given(
    parsers.parse(
        '稽核事件："{actor}" 將 "{bot_id}" 的 "{field}" 從 "{before}" 改為 "{after}"'
    )
)
def bot_event(context, actor, bot_id, field, before, after):
    context["entry"] = _entry(
        entity_type="bot", entity_id=bot_id, actor_user_id=actor,
        changed_fields={field: {"before": before, "after": after}},
    )


@given(parsers.parse('機器人 "{bot_id}" 名稱為 "{name}"'))
def bot_name(context, bot_id, name):
    context["bots"][bot_id] = Bot(
        id=BotId(value=bot_id), tenant_id="t-001", name=name,
    )


@given(
    parsers.parse(
        '平台稽核事件：對租戶 "{tenant_id}" 的防護設定將 "{field}" '
        '從 "{before}" 改為 "{after}"'
    )
)
def platform_guard_event(context, tenant_id, field, before, after):
    context["entry"] = _entry(
        entity_type="guard_settings", entity_id=f"tenant:{tenant_id}",
        tenant_id=tenant_id, actor_user_id="u-sys", source="platform",
        changed_fields={
            field: {"before": before.split(","), "after": after.split(",")}
        },
    )


@given(
    parsers.parse(
        '稽核事件："{actor}" 將 "{bot_id}" 底下 worker "{worker_id}" 的 "{field}" '
        "從 {n0:d} 字改為 {n1:d} 字"
    )
)
def worker_long_text_event(context, actor, bot_id, worker_id, field, n0, n1):
    context["entry"] = _entry(
        entity_type="worker", entity_id=worker_id, actor_user_id=actor,
        parent_entity_type="bot", parent_entity_id=bot_id,
        changed_fields={field: {"before": "x" * n0, "after": "y" * n1}},
    )


@given(parsers.parse('worker "{worker_id}" 名稱為 "{name}"'))
def worker_name(context, worker_id, name):
    context["workers"][worker_id] = WorkerConfig(
        id=worker_id, bot_id="bot-001", name=name,
    )


@given(
    parsers.parse(
        '稽核事件：平台 system prompt "{entity_id}" 的 "{field}" '
        '從 "{before}" 改為 "{after}"（無租戶）'
    )
)
def platform_prompt_event(context, entity_id, field, before, after):
    context["entry"] = _entry(
        entity_type="system_prompt", entity_id=entity_id, tenant_id=None,
        actor_user_id="u-sys",
        changed_fields={field: {"before": before, "after": after}},
    )


# ── recorder hook ──


@given("稽核紀錄器掛上會拋例外的通知掛勾")
def recorder_with_failing_hook(context):
    async def _boom(entry):
        raise RuntimeError("teams down")

    context["hook_calls"] = []
    context["recorder"] = AuditRecorder(
        repository=context["audit_repo"], on_recorded=_boom,
    )


@given("稽核紀錄器掛上可觀察的通知掛勾")
def recorder_with_observed_hook(context):
    calls: list = []

    async def _hook(entry):
        calls.append(entry)

    context["hook_calls"] = calls
    context["recorder"] = AuditRecorder(
        repository=context["audit_repo"], on_recorded=_hook,
    )


# ── When ──


@when(parsers.parse('判定變更欄位 "{fields}" 所屬群組'))
def compute_groups(context, fields):
    context["groups"] = groups_touched([f for f in fields.split(",") if f])


@when("派發設定變更通知")
def dispatch(context):
    uc = DispatchConfigChangeNotificationUseCase(
        channel_repo=context["channel_repo"],
        tenant_repository=context["tenant_repo"],
        dispatcher=context["dispatcher"],
        user_repository=context["user_repo"],
        bot_repository=context["bot_repo"],
        worker_repository=context["worker_repo"],
    )
    context["sent_count"] = _run(uc.execute(context["entry"]))


@when(
    parsers.parse(
        '稽核紀錄器記錄 "{entity_id}" 的 "{field}" 從 "{before}" 改為 "{after}"'
    )
)
def recorder_record(context, entity_id, field, before, after):
    try:
        context["recorded"] = _run(context["recorder"].record(
            entity_type="bot", entity_id=entity_id, action="update",
            before={field: before}, after={field: after},
            actor_user_id="u-001", tenant_id="t-001",
        ))
        context["error"] = None
    except Exception as e:  # noqa: BLE001 — 驗證 fail-open 用
        context["error"] = e


def _parse_groups(text: str):
    if text == "null":
        return None
    return [g for g in text.split(",") if g]


@when(
    parsers.re(
        r'租戶 "(?P<actor_tenant>[^"]+)" 的 "(?P<role>[^"]+)" "(?P<actor>[^"]+)" '
        r'將租戶 "(?P<tenant_id>[^"]+)" 的通知群組設為 (?P<groups>".*"|null)'
    )
)
def update_preferences(context, actor_tenant, role, actor, tenant_id, groups):
    uc = UpdateTenantNotificationPreferencesUseCase(
        tenant_repository=context["tenant_repo"],
        audit=AuditRecorder(repository=context["audit_repo"]),
    )
    try:
        context["pref"] = _run(uc.execute(
            tenant_id=tenant_id,
            groups=_parse_groups(groups.strip('"')),
            actor_role=role,
            actor_tenant_id=actor_tenant,
            actor_user_id=actor,
        ))
        context["error"] = None
    except (PermissionError, ValidationError) as e:
        context["error"] = e


@when(parsers.parse('讀取租戶 "{tenant_id}" 的通知偏好'))
def read_preferences(context, tenant_id):
    uc = GetTenantNotificationPreferencesUseCase(
        tenant_repository=context["tenant_repo"],
    )
    context["pref"] = _run(uc.execute(tenant_id=tenant_id))


# ── Then ──


@then(parsers.re(r'觸及的群組應為 "(?P<groups>[^"]*)"$'))
def check_groups(context, groups):
    assert context["groups"] == [g for g in groups.split(",") if g]


def _sent_to(context, name: str):
    return [s for s in context["sent"] if s[0] == name]


@then(parsers.parse('渠道 "{name}" 應收到 {count:d} 則通知'))
def check_sent_count(context, name, count):
    assert len(_sent_to(context, name)) == count, context["sent"]


@then(parsers.parse('渠道 "{name}" 不應收到通知'))
def check_not_sent_to(context, name):
    assert not _sent_to(context, name)


@then("不應發送任何通知")
def check_nothing_sent(context):
    assert context["sent"] == []
    assert context["sent_count"] == 0


@then(parsers.parse('通知主旨應含 "{text}"'))
def check_subject(context, text):
    assert any(text in s[1] for s in context["sent"]), context["sent"]


@then(parsers.re(r'通知內容應含 "(?P<a>[^"]+)" 與 "(?P<b>[^"]+)"$'))
def check_body_two(context, a, b):
    body = context["sent"][0][2]
    assert a in body and b in body, body


@then(parsers.re(r'通知內容應含 "(?P<text>[^"]+)"$'))
def check_body(context, text):
    assert any(text in s[2] for s in context["sent"]), context["sent"]


@then(parsers.re(r'通知內容不應含 "(?P<text>[^"]+)"$'))
def check_body_absent(context, text):
    assert all(text not in s[2] for s in context["sent"]), context["sent"]


@then(parsers.re(r'通知內容不應含全文 "(?P<text>[^"]+)"$'))
def check_body_no_fulltext(context, text):
    assert all(text not in s[2] for s in context["sent"]), context["sent"]


@then("稽核列仍應寫入")
def check_audit_written(context):
    context["audit_repo"].append.assert_awaited_once()


@then("記錄呼叫不應拋出例外")
def check_no_error(context):
    assert context["error"] is None
    assert context["recorded"] is not None


@then("通知掛勾應收到該筆稽核列")
def check_hook_called(context):
    assert context["hook_calls"] == [context["recorded"]]


@then("通知掛勾不應被呼叫")
def check_hook_not_called(context):
    assert context["hook_calls"] == []
    assert context["recorded"] is None


@then(parsers.parse('租戶 "{tenant_id}" 的通知群組應為 "{groups}"'))
def check_tenant_groups(context, tenant_id, groups):
    assert context["error"] is None, context["error"]
    expected = [g for g in groups.split(",") if g]
    assert context["tenants"][tenant_id].config_change_notify_fields == expected
    assert context["pref"].fields == expected


@then(parsers.parse('租戶 "{tenant_id}" 的通知群組應為平台預設 "{groups}"'))
def check_tenant_default_groups(context, tenant_id, groups):
    assert context["error"] is None, context["error"]
    assert context["tenants"][tenant_id].config_change_notify_fields is None
    assert context["pref"].fields is None
    assert context["pref"].effective == [g for g in groups.split(",") if g]
    assert list(DEFAULT_NOTIFY_GROUPS) == context["pref"].effective


@then(
    parsers.parse(
        '應寫入 entity_type "{etype}" 的 update 稽核，tenant_id 為 "{tenant_id}"'
    )
)
def check_pref_audit(context, etype, tenant_id):
    entries = [c.args[0] for c in context["audit_repo"].append.await_args_list]
    match = [e for e in entries if e.entity_type == etype]
    assert match, entries
    assert match[0].action == "update"
    assert match[0].tenant_id == tenant_id
    assert "config_change_notify_fields" in match[0].changed_fields


@then("應拋出 PermissionError")
def check_permission_error(context):
    assert isinstance(context["error"], PermissionError)


@then("應拋出 ValidationError")
def check_validation_error(context):
    assert isinstance(context["error"], ValidationError)


@then("不應寫入任何稽核")
def check_no_audit(context):
    context["audit_repo"].append.assert_not_awaited()


@then(parsers.parse('通知偏好的 fields 應為 "{groups}"'))
def check_pref_fields(context, groups):
    assert context["pref"].fields == [g for g in groups.split(",") if g]


@then(parsers.parse("通知偏好的 available_groups 應含 {names} 且各有標籤"))
def check_available_groups(context, names):
    expected = [n.strip().strip('"') for n in names.split(",")]
    available = {g.key: g.label for g in context["pref"].available_groups}
    for key in expected:
        assert key in available, available
        assert available[key], key
