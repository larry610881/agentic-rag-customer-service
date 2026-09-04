"""異常控管告警與通知 BDD Step Definitions（Issue #68 P7c）"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.abuse.abuse_alerts import AbuseAlertService
from src.application.abuse.abuse_control_service import AbuseControlService
from src.application.abuse.abuse_report import summarize_entries
from src.application.observability.notification_use_cases import (
    DispatchAbuseNotificationUseCase,
    NotificationDispatcher,
)
from src.domain.abuse.events import AbuseAlertEvent, AbuseAlertKind
from src.domain.abuse.policy import AbuseLevel, AbusePolicy, AbuseSubject, SubjectKind
from src.domain.audit.entity import AuditEntry
from src.domain.observability.notification import NotificationChannel
from src.infrastructure.abuse.in_memory_abuse_score_store import (
    InMemoryAbuseScoreStore,
)
from src.infrastructure.notification.teams_workflow_sender import (
    TeamsWorkflowSender,
)

scenarios("unit/abuse/abuse_alerts.feature")

_T = "t1"


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


@pytest.fixture
def ctx():
    return {"events": []}


# ---------------------------------------------------------------------------
# AbuseAlertService
# ---------------------------------------------------------------------------


@given("告警服務與記憶體儲存")
def alert_service(ctx):
    async def publish(event: AbuseAlertEvent) -> None:
        ctx["events"].append(event)

    ctx["alert_store"] = InMemoryAbuseScoreStore()
    ctx["alerts"] = AbuseAlertService(ctx["alert_store"], publish)


@given("控管服務的分數儲存失效")
def control_store_fails(ctx):
    store = InMemoryAbuseScoreStore()
    store.fail = True
    ctx["control"] = AbuseControlService(store, AbusePolicy(), alerts=ctx["alerts"])


@when(parsers.parse(
    '訪客 "{vid}" 在通路 "{channel}" 升到等級 {level:d}，原因 "{reason}"'
))
def escalate(ctx, vid, channel, level, reason):
    _run(ctx["alerts"].escalated(
        _T, AbuseSubject(SubjectKind.VISITOR, vid), AbuseLevel(level),
        reasons=(reason,), retry_after=900, channel=channel,
    ))


@when(parsers.parse("租戶被限流 {n:d} 次"))
def rate_limited(ctx, n):
    for _ in range(n):
        _run(ctx["alerts"].rate_limited(_T))


@when(parsers.parse('控管服務評估訪客 "{vid}" 兩次'))
def evaluate_twice(ctx, vid):
    for _ in range(2):
        _run(ctx["control"].evaluate(_T, AbuseSubject(SubjectKind.VISITOR, vid)))


def _events(ctx, kind: str) -> list[AbuseAlertEvent]:
    return [e for e in ctx["events"] if e.kind == AbuseAlertKind(kind)]


@then(parsers.parse('應發出 {n:d} 則 "{kind}" 事件'))
def events_count(ctx, n, kind):
    assert len(_events(ctx, kind)) == n, ctx["events"]


@then(parsers.parse('事件的主體為 "{subject}" 且不含完整 id'))
def event_subject(ctx, subject):
    e = _events(ctx, "escalation")[0]
    assert f"{e.subject_kind} {e.subject_masked}" == subject
    assert "visitor-abcdef-123456" not in json.dumps(e.__dict__, default=str)


@then(parsers.parse("事件的等級為 {level:d} 且 retry_after 大於 0"))
def event_level(ctx, level):
    e = _events(ctx, "escalation")[0]
    assert e.level == level and e.retry_after > 0


@then(parsers.parse('事件摘要含 "{text}"'))
def event_summary(ctx, text):
    assert any(text in line for line in ctx["events"][0].summary_lines)


# ---------------------------------------------------------------------------
# Teams sender
# ---------------------------------------------------------------------------


def _teams_channel(config: dict) -> NotificationChannel:
    return NotificationChannel(
        id="ch-teams", channel_type="teams", name="teams", enabled=True,
        config_encrypted=json.dumps(config),
    )


def _mock_transport(ctx):
    def handler(request: httpx.Request) -> httpx.Response:
        ctx["requests"].append(json.loads(request.content))
        return httpx.Response(202)

    return httpx.MockTransport(handler)


@given("設定了 webhook_url 的 Teams 渠道與攔截的 HTTP 傳輸")
def teams_configured(ctx):
    ctx["requests"] = []
    ctx["channel"] = _teams_channel({"webhook_url": "https://prod.logic.azure.com/x"})
    ctx["sender"] = TeamsWorkflowSender(transport=_mock_transport(ctx))


@given("未設定 webhook_url 的 Teams 渠道與攔截的 HTTP 傳輸")
def teams_unconfigured(ctx):
    ctx["requests"] = []
    ctx["channel"] = _teams_channel({})
    ctx["sender"] = TeamsWorkflowSender(transport=_mock_transport(ctx))


@when(parsers.parse('送出 Teams 通知 主旨 "{subject}" 內文 "{body}"'))
def send_teams(ctx, subject, body):
    _run(ctx["sender"].send(ctx["channel"], subject, body.replace("\\n", "\n")))


@then(parsers.parse('Teams 收到 type "{mtype}" 且附件 contentType 為 "{ctype}"'))
def teams_payload(ctx, mtype, ctype):
    payload = ctx["requests"][0]
    assert payload["type"] == mtype
    assert payload["attachments"][0]["contentType"] == ctype
    assert payload["attachments"][0]["content"]["type"] == "AdaptiveCard"


@then(parsers.parse('Adaptive Card 含 FactSet 事實 "{title}" 為 "{value}"'))
def teams_fact(ctx, title, value):
    body = ctx["requests"][0]["attachments"][0]["content"]["body"]
    facts = [f for b in body if b["type"] == "FactSet" for f in b["facts"]]
    assert {"title": title, "value": value} in facts, facts


@then("Teams 未收到任何請求")
def teams_no_request(ctx):
    assert ctx["requests"] == []


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


@given("分派器掛了會解密的加密服務、一個會丟例外的 email 發送器與一個 teams 發送器")
def dispatcher_with_enc(ctx):
    enc = MagicMock()
    enc.decrypt.side_effect = lambda raw: json.dumps({"recipients": ["a@b.c"]})
    email = AsyncMock()
    email.send.side_effect = RuntimeError("smtp down")
    teams = AsyncMock()
    ctx["email_sender"], ctx["teams_sender"] = email, teams
    ctx["dispatcher"] = NotificationDispatcher(
        senders={"email": email, "teams": teams}, encryption_service=enc
    )


@when("對加密設定的 email 渠道與 teams 渠道各送一則通知")
def dispatch_two(ctx):
    email_ch = NotificationChannel(
        id="e", channel_type="email", name="e", enabled=True,
        config_encrypted="ENCRYPTED-BLOB",
    )
    teams_ch = _teams_channel({"webhook_url": "https://x"})
    _run(ctx["dispatcher"].send_to_channel(email_ch, "s", "b"))
    _run(ctx["dispatcher"].send_to_channel(teams_ch, "s", "b"))


@then("email 發送器收到的設定為明文 JSON")
def email_plain(ctx):
    channel = ctx["email_sender"].send.await_args.args[0]
    assert json.loads(channel.config_encrypted)["recipients"] == ["a@b.c"]


@then("teams 發送器仍被呼叫")
def teams_called(ctx):
    ctx["teams_sender"].send.assert_awaited_once()


# ---------------------------------------------------------------------------
# DispatchAbuseNotificationUseCase
# ---------------------------------------------------------------------------


@given("兩個啟用渠道，其中一個 notify_abuse 關閉")
def two_channels(ctx):
    on = NotificationChannel(id="on", channel_type="teams", name="on", enabled=True,
                             config_encrypted="{}", notify_abuse=True)
    off = NotificationChannel(id="off", channel_type="teams", name="off", enabled=True,
                              config_encrypted="{}", notify_abuse=False)
    repo = AsyncMock()
    repo.list_enabled.return_value = [on, off]
    throttle = AsyncMock()
    throttle.is_throttled.return_value = False
    ctx["dispatcher"] = AsyncMock()
    ctx["uc"] = DispatchAbuseNotificationUseCase(repo, throttle, ctx["dispatcher"])


@when(parsers.parse('分派一則 escalation 告警（主體 "{sid}"）'))
def dispatch_alert(ctx, sid):
    from src.domain.abuse.events import mask_subject_id

    event = AbuseAlertEvent(
        kind=AbuseAlertKind.ESCALATION, tenant_id=_T, fingerprint="fp", level=3,
        subject_kind="visitor", subject_masked=mask_subject_id(sid), channel="widget",
        reasons=("guard_hit",), retry_after=900,
    )
    ctx["sent"] = _run(ctx["uc"].execute(event))


@then("只有 notify_abuse 的渠道收到通知")
def only_on(ctx):
    calls = ctx["dispatcher"].send_to_channel.await_args_list
    assert ctx["sent"] == 1 and [c.args[0].id for c in calls] == ["on"]


@then(parsers.parse('通知內文含 "{masked}" 且不含 "{raw}"'))
def body_masked(ctx, masked, raw):
    body = ctx["dispatcher"].send_to_channel.await_args.args[2]
    assert masked in body and raw not in body


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


_RAW_ID = "visitor-abcdef-123456"


def _entry(action: str, level: int | None, age_hours: float, sid: str = _RAW_ID):
    return AuditEntry(
        entity_type="abuse_control", entity_id=f"abuse:{_T}:visitor:{sid}",
        action=action, tenant_id=_T,
        changed_fields={"level": {"before": 0, "after": level}} if level else {},
        created_at=datetime.now(timezone.utc) - timedelta(hours=age_hours),
    )


@given(
    "過去 24 小時的稽核紀錄：L3 升級 2 次、L2 升級 3 次、解除 1 次、更早的 L3 升級 5 次"
)
def report_entries(ctx):
    ctx["entries"] = (
        [_entry("escalate", 3, 1), _entry("escalate", 3, 2)]
        + [_entry("escalate", 2, 3, sid=f"u{i}") for i in range(3)]
        + [_entry("release", None, 4)]
        + [_entry("escalate", 3, 30 + i) for i in range(5)]
    )


@when("彙整摘要")
def summarize(ctx):
    ctx["lines"] = summarize_entries(
        ctx["entries"], since=datetime.now(timezone.utc) - timedelta(hours=24),
        fail_open_count=0,
    )


@then(parsers.parse('摘要含 "{a}" 與 "{b}"'))
def summary_contains(ctx, a, b):
    text = "\n".join(ctx["lines"])
    assert a in text and b in text, text


@then("摘要的 Top 主體不含完整 id")
def summary_masked(ctx):
    text = "\n".join(ctx["lines"])
    assert "visitor-abcdef-123456" not in text and "visi…56" in text
