"""Gate Run 生命週期 BDD Step Definitions

背景執行器以 monkeypatch 換掉 AgentAPIClient（不打 HTTP），
repos 一律 AsyncMock + in-memory store。
"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

import prompt_optimizer.api_client as api_client_module
from prompt_optimizer.api_client import ChatResult
from src.application.prompt_gate.gate_run_use_cases import (
    CleanupOrphanGateRunsUseCase,
    GateCase,
    StartGateRunUseCase,
)
from src.application.prompt_gate.version_use_cases import (
    PublishConfigVersionUseCase,
)
from src.domain.bot.entity import Bot
from src.domain.bot.repository import BotRepository
from src.domain.bot.value_objects import BotId
from src.domain.prompt_gate.config_snapshot import take_snapshot
from src.domain.prompt_gate.entity import (
    STATUS_DRAFT,
    STATUS_PENDING_PUBLISH,
    STATUS_PUBLISHED,
    STATUS_VALIDATING,
    VERDICT_FAIL,
    VERDICT_FORCED,
    VERDICT_PASS,
    VERDICT_SKIPPED,
    BotConfigVersion,
    GateBlockedError,
)
from src.domain.prompt_gate.gate_run_entity import (
    RUN_COMPLETED,
    RUN_ERROR,
    RUN_QUEUED,
    RUN_RUNNING,
    PromptGateRun,
)
from src.domain.prompt_gate.gate_run_repository import (
    PromptGateRunRepository,
)
from src.domain.prompt_gate.repository import BotConfigVersionRepository
from src.domain.tenant.entity import Tenant
from src.domain.tenant.repository import TenantRepository

scenarios("unit/prompt_gate/gate_run_lifecycle.feature")

BOT_ID = "bot-1"
TENANT = "t1"


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


class _FakeClient:
    """回答固定通過/失敗 contains_all 的假 AgentAPIClient。"""

    answer = "正常回答內容"

    def __init__(self, *args, **kwargs):
        pass

    async def chat(self, **kwargs):
        return ChatResult(
            answer=self.answer, conversation_id="c", tool_calls=[],
            sources=[], usage={
                "estimated_cost": 0.001, "input_tokens": 100,
                "output_tokens": 50, "total_tokens": 150,
            },
            latency_ms=10, trace_id="tr", trace_nodes=[],
        )

    async def close(self):
        pass


def _stores(context, bot):
    version = BotConfigVersion(
        id="ver-1", tenant_id=TENANT, bot_id=BOT_ID, version_no=2,
        config_snapshot=take_snapshot(bot), status=STATUS_VALIDATING,
        gate_run_id="run-1", changed_fields=["base_prompt"],
    )
    run = PromptGateRun(
        id="run-1", tenant_id=TENANT, bot_id=BOT_ID,
        version_id="ver-1", status=RUN_QUEUED,
    )

    version_repo = AsyncMock(spec=BotConfigVersionRepository)
    gate_repo = AsyncMock(spec=PromptGateRunRepository)

    async def _find_v(vid, tid):
        return version if vid == version.id and tid == TENANT else None

    async def _find_r(rid, tid):
        return run if rid == run.id and tid == TENANT else None

    version_repo.find_by_id.side_effect = _find_v
    gate_repo.find_by_id.side_effect = _find_r
    context.update(version=version, run=run,
                   version_repo=version_repo, gate_repo=gate_repo)
    return version_repo, gate_repo


def _build_start_uc(context, bot):
    version_repo, gate_repo = _stores(context, bot)
    uc = StartGateRunUseCase(
        bot_repository=AsyncMock(spec=BotRepository),
        tenant_repository=AsyncMock(spec=TenantRepository),
        version_repository=version_repo,
        gate_run_repository=gate_repo,
        eval_dataset_repository=AsyncMock(),
        gate_run_repo_factory=lambda: gate_repo,
        version_repo_factory=lambda: version_repo,
    )
    context["uc"] = uc


def _bg_kwargs(context, cases):
    return {
        "run_id": "run-1", "tenant_id": TENANT, "bot_id": BOT_ID,
        "version_id": "ver-1",
        "config_snapshot": context["version"].config_snapshot,
        "cases": cases, "repeats": 2, "soft_threshold": 0.8,
        "budget_usd": 10.0, "api_token": "jwt",
    }


@given("一個 validating 中的版本與其 gate run")
def validating_version(context):
    bot = Bot(id=BotId(value=BOT_ID), tenant_id=TENANT, name="b")
    _build_start_uc(context, bot)


@when("gate run 以 PASS 完成")
def run_pass(context, monkeypatch):
    monkeypatch.setattr(api_client_module, "AgentAPIClient", _FakeClient)
    cases = [GateCase(
        case_id="d:c1", question="q", priority="P0",
        assertions=[{"type": "contains_all", "params": {"keywords": ["正常"]}}],
    )]
    _run(context["uc"]._execute_background(**_bg_kwargs(context, cases)))


@when("gate run 以 FAIL 完成（原因 hard_gate）")
def run_fail(context, monkeypatch):
    monkeypatch.setattr(api_client_module, "AgentAPIClient", _FakeClient)
    cases = [GateCase(
        case_id="d:c1", question="q", priority="P0",
        assertions=[{
            "type": "tool_was_called", "params": {"tool_name": "rag_query"},
        }],
    )]
    _run(context["uc"]._execute_background(**_bg_kwargs(context, cases)))


@when("gate run 執行中拋出例外")
def run_exception(context, monkeypatch):
    class _Boom:
        def __init__(self, *a, **k):
            raise RuntimeError("api client init failed")

    monkeypatch.setattr(api_client_module, "AgentAPIClient", _Boom)
    cases = [GateCase(case_id="d:c1", question="q", priority="P0")]
    _run(context["uc"]._execute_background(**_bg_kwargs(context, cases)))


@then(parsers.parse("run 狀態為 completed 且 verdict 為 {verdict}"))
def verify_run_completed(context, verdict):
    assert context["run"].status == RUN_COMPLETED
    assert context["run"].verdict == verdict


@then(parsers.parse("版本狀態為 pending_publish 且 gate_verdict 為 {v}"))
def verify_version_pending(context, v):
    assert context["version"].status == STATUS_PENDING_PUBLISH
    assert context["version"].gate_verdict == v


@then(parsers.parse("版本狀態為 draft 且 gate_verdict 為 {v}"))
def verify_version_draft_fail(context, v):
    assert context["version"].status == STATUS_DRAFT
    assert context["version"].gate_verdict == v


@then("run 狀態為 error")
def verify_run_error(context):
    assert context["run"].status == RUN_ERROR


@then("版本狀態為 draft")
def verify_version_draft(context):
    assert context["version"].status == STATUS_DRAFT


# ─── publish 分支 ───


def _publish_setup(context, *, gate_mode, status, gate_verdict):
    bot = Bot(
        id=BotId(value=BOT_ID), tenant_id=TENANT, name="b",
        gate_mode=gate_mode,
    )
    version = BotConfigVersion(
        id="ver-1", tenant_id=TENANT, bot_id=BOT_ID, version_no=2,
        config_snapshot=take_snapshot(bot), status=status,
        gate_verdict=gate_verdict, changed_fields=["base_prompt"],
    )
    bot_repo = AsyncMock(spec=BotRepository)
    bot_repo.find_by_id.return_value = bot
    version_repo = AsyncMock(spec=BotConfigVersionRepository)
    version_repo.find_by_id.return_value = version
    tenant_repo = AsyncMock(spec=TenantRepository)
    tenant_repo.find_by_id.return_value = Tenant(
        name="t", prompt_gate_enabled=True
    )
    context["publish_uc"] = PublishConfigVersionUseCase(
        bot_repository=bot_repo,
        version_repository=version_repo,
        tenant_repository=tenant_repo,
    )
    context["version"] = version


@given("一個 pending_publish 且 verdict 為 pass 的版本")
def pending_version(context):
    _publish_setup(
        context, gate_mode="block",
        status=STATUS_PENDING_PUBLISH, gate_verdict=VERDICT_PASS,
    )


@given(parsers.parse(
    "bot gate_mode 為 {mode} 且版本為 draft 且 gate_verdict 為 fail"
))
def draft_failed_version(context, mode):
    _publish_setup(
        context, gate_mode=mode,
        status=STATUS_DRAFT, gate_verdict=VERDICT_FAIL,
    )


@given("bot gate_mode 為 block 且版本為 draft 且從未驗證")
def draft_unvalidated(context):
    _publish_setup(
        context, gate_mode="block",
        status=STATUS_DRAFT, gate_verdict=None,
    )


@given("bot gate_mode 為 off 且版本為 draft")
def draft_gate_off(context):
    _publish_setup(
        context, gate_mode="off",
        status=STATUS_DRAFT, gate_verdict=None,
    )


@when("發布該版本")
def publish(context):
    try:
        _run(context["publish_uc"].execute(TENANT, "ver-1"))
    except GateBlockedError as exc:
        context["error"] = exc


@when("以 force 發布該版本")
def publish_force(context):
    try:
        _run(context["publish_uc"].execute(TENANT, "ver-1", force=True))
    except GateBlockedError as exc:
        context["error"] = exc


@then(parsers.parse("版本狀態為 published 且 gate_verdict 為 {v}"))
def verify_published(context, v):
    expected = {
        "pass": VERDICT_PASS, "forced": VERDICT_FORCED,
        "skipped": VERDICT_SKIPPED,
    }[v]
    assert context["version"].status == STATUS_PUBLISHED
    assert context["version"].gate_verdict == expected


@then("發布被拒絕（閘門未通過）")
def verify_publish_blocked(context):
    assert isinstance(context["error"], GateBlockedError)
    assert context["version"].status != STATUS_PUBLISHED


# ─── 孤兒清理 ───


@given("一筆 running 中的 gate run 與其 validating 版本（模擬重啟遺留）")
def orphan_setup(context):
    run = PromptGateRun(
        id="run-9", tenant_id=TENANT, bot_id=BOT_ID,
        version_id="ver-9", status=RUN_RUNNING,
    )
    version = BotConfigVersion(
        id="ver-9", tenant_id=TENANT, bot_id=BOT_ID, version_no=3,
        status=STATUS_VALIDATING, gate_run_id="run-9",
    )
    gate_repo = AsyncMock(spec=PromptGateRunRepository)
    version_repo = AsyncMock(spec=BotConfigVersionRepository)

    async def _mark_orphans():
        run.mark_error("orphaned by process restart")
        return [version.id]

    async def _revert(ids):
        if version.id in ids and version.status == STATUS_VALIDATING:
            version.status = STATUS_DRAFT
            version.gate_run_id = None
            return 1
        return 0

    gate_repo.mark_orphans_error.side_effect = _mark_orphans
    version_repo.revert_validating_to_draft.side_effect = _revert
    context["run"] = run
    context["version"] = version
    context["cleanup_uc"] = CleanupOrphanGateRunsUseCase(
        gate_run_repository=gate_repo, version_repository=version_repo
    )


@when("執行孤兒清理")
def do_cleanup(context):
    context["cleaned"] = _run(context["cleanup_uc"].execute())


def test_cleanup_reverts_stale_validating_when_no_orphan_runs():
    """M5：run 已 completed 但版本卡 validating（非同交易寫入間進程被砍）——
    mark_orphans_error 撈不到（沒有 queued/running run），仍須靠 stale 掃描救回。"""
    gate_repo = AsyncMock(spec=PromptGateRunRepository)
    version_repo = AsyncMock(spec=BotConfigVersionRepository)
    gate_repo.mark_orphans_error.return_value = []  # 無孤兒 run
    version_repo.revert_stale_validating_versions.return_value = 1

    uc = CleanupOrphanGateRunsUseCase(
        gate_run_repository=gate_repo, version_repository=version_repo
    )
    _run(uc.execute())

    # 關鍵：即使沒有孤兒 run，仍呼叫 stale 掃描把卡住的版本退回 draft
    version_repo.revert_stale_validating_versions.assert_awaited_once()
