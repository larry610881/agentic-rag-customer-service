"""異常分數與分級 BDD Step Definitions（Issue #68 P7a）

service + 記憶體儲存 + 假時鐘。
"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.abuse.abuse_control_service import (
    AbuseControlService,
    apply_conservative_mode,
)
from src.domain.abuse.policy import (
    CONSERVATIVE_PROMPT_SUFFIX,
    AbuseMode,
    AbusePolicy,
    AbuseSubject,
    SubjectKind,
)
from src.infrastructure.abuse.in_memory_abuse_score_store import (
    InMemoryAbuseScoreStore,
)

scenarios("unit/abuse/abuse_scoring.feature")

_T = "t1"


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


@pytest.fixture
def ctx():
    return {}


@given("記憶體版異常分數儲存與預設政策")
def setup(ctx):
    ctx["now"] = 1_000_000.0
    ctx["store"] = InMemoryAbuseScoreStore(clock=lambda: ctx["now"])
    ctx["policy"] = AbusePolicy()
    ctx["audit"] = AsyncMock()
    ctx["svc"] = AbuseControlService(ctx["store"], ctx["policy"], audit=ctx["audit"])


@given("異常分數儲存失效")
def store_fails(ctx):
    ctx["store"].fail = True


@given(parsers.parse('政策模式為 "{mode}"'))
def policy_mode(ctx, mode):
    ctx["policy"].mode = AbuseMode(mode)


def _subject(kind: str, sid: str) -> AbuseSubject:
    return AbuseSubject(SubjectKind(kind), sid)


def _record(ctx, subject, **signals):
    ctx["decision"] = _run(ctx["svc"].record(_T, subject, **signals))
    return ctx["decision"]


@when(parsers.parse('訪客 "{vid}" 一回合 Guard 命中'))
def one_guard_hit(ctx, vid):
    _record(ctx, _subject("visitor", vid), guard_hit=True)


@when(parsers.parse('訪客 "{vid}" 連續 {n:d} 回合 Guard 命中'))
def n_guard_hits(ctx, vid, n):
    for _ in range(n):
        _record(ctx, _subject("visitor", vid), guard_hit=True)
        ctx["now"] += 10


@when(parsers.parse('主體 "{kind}" "{sid}" 連續 {n:d} 回合 Guard 命中'))
def n_guard_hits_kind(ctx, kind, sid, n):
    for _ in range(n):
        _record(ctx, _subject(kind, sid), guard_hit=True)
        ctx["now"] += 5


@when(parsers.parse('訪客 "{vid}" 一分鐘內送出 {n:d} 句正常訊息'))
def burst(ctx, vid, n):
    for _ in range(n):
        _record(ctx, _subject("visitor", vid))
        ctx["now"] += 1


@when(parsers.parse("時間經過 {minutes:d} 分鐘"))
def time_passes(ctx, minutes):
    ctx["now"] += minutes * 60


@when(parsers.parse('訪客 "{vid}" 連續 {n:d} 回合無法分流'))
def unrouted(ctx, vid, n):
    for _ in range(n):
        _record(ctx, _subject("visitor", vid), unrouted=True)
        ctx["now"] += 2


@when(parsers.parse('訪客 "{vid}" 一回合正常分流'))
def routed(ctx, vid):
    _record(ctx, _subject("visitor", vid), unrouted=False)


@when(parsers.parse('管理員 "{actor}" 解除訪客 "{vid}"'))
def release(ctx, actor, vid):
    _run(ctx["svc"].release(_T, _subject("visitor", vid), actor_user_id=actor))


@when("對 bot 設定套用保守模式")
def conservative(ctx):
    ctx["cfg"] = apply_conservative_mode({
        "enabled_tools": ["search_knowledge"], "rag_top_k": 6,
        "system_prompt": "你是客服", "mcp_servers": [{"name": "x"}],
    })


def _evaluate(ctx, kind, sid):
    ctx["decision"] = _run(ctx["svc"].evaluate(_T, _subject(kind, sid)))
    return ctx["decision"]


@then(parsers.parse('訪客 "{vid}" 的等級為 {level:d}'))
def visitor_level(ctx, vid, level):
    assert int(_evaluate(ctx, "visitor", vid).level) == level, ctx["decision"]


@then(parsers.parse('主體 "{kind}" "{sid}" 的等級為 {level:d}'))
def subject_level(ctx, kind, sid, level):
    assert int(_evaluate(ctx, kind, sid).level) == level, ctx["decision"]


@then(parsers.parse('訪客 "{vid}" 的決定為保守模式'))
def decision_conservative(ctx, vid):
    d = _evaluate(ctx, "visitor", vid)
    assert d.conservative and not d.fixed_reply and not d.blocked


@then(parsers.parse('訪客 "{vid}" 的決定為固定文案 retry_after {retry:d}'))
def decision_fixed(ctx, vid, retry):
    d = _evaluate(ctx, "visitor", vid)
    assert d.fixed_reply and d.reply_text == "請稍後再試"
    assert 0 < d.retry_after <= retry


@then(parsers.parse('訪客 "{vid}" 的決定為拒絕'))
def decision_blocked(ctx, vid):
    d = _evaluate(ctx, "visitor", vid)
    assert d.blocked and d.reply_text == "AI 助手暫時休息，請稍後再試"
    assert d.retry_after > 0


@then(parsers.parse('訪客 "{vid}" 的決定為放行'))
def decision_pass(ctx, vid):
    d = _evaluate(ctx, "visitor", vid)
    assert d.effective_level == 0
    assert not (d.conservative or d.fixed_reply or d.blocked)


@then(parsers.parse('訪客 "{vid}" 的分數低於 {value:g}'))
def score_below(ctx, vid, value):
    assert _evaluate(ctx, "visitor", vid).score < value


@then(parsers.parse('訪客 "{vid}" 的分數為 {value:g}'))
def score_is(ctx, vid, value):
    assert abs(_evaluate(ctx, "visitor", vid).score - value) < 0.5


@then(parsers.parse('稽核應記錄 "{entity}" 的 "{action}" 到等級 {level:d}'))
def audit_escalate(ctx, entity, action, level):
    calls = [c.kwargs for c in ctx["audit"].record.await_args_list]
    assert any(
        c["entity_type"] == entity and c["action"] == action
        and c["after"]["level"] == level for c in calls
    ), calls


@then(parsers.parse('稽核應記錄 "{entity}" 的 "{action}"'))
def audit_action(ctx, entity, action):
    calls = [c.kwargs for c in ctx["audit"].record.await_args_list]
    assert any(c["entity_type"] == entity and c["action"] == action for c in calls)


@then("bot 設定的 enabled_tools 為空、rag_top_k 由 6 變 3、system_prompt 含保守指令")
def conservative_applied(ctx):
    cfg = ctx["cfg"]
    assert cfg["enabled_tools"] == [] and cfg["mcp_servers"] == []
    assert cfg["rag_top_k"] == 3
    assert CONSERVATIVE_PROMPT_SUFFIX in cfg["system_prompt"]
