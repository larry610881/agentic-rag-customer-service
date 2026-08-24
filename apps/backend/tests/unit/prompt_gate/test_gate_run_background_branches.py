"""Regression: gate run 背景執行的三條關鍵分支（M52）。

(1) 預算中止：actual_cost 超過 budget_usd → aborted=True、後續 round 不再跑。
(2) API 錯誤：chat 拋例外 → 空 ChatResult + api_error 硬斷言 → verdict FAIL
    （run 正常 completed，非 background_error）。
(3) Round 2+ 只跑 P0（定案 7）：P0+P1 各一題、repeats=2 → chat 共 3 次而非 4 次。
"""

import asyncio
from unittest.mock import AsyncMock

import prompt_optimizer.api_client as api_client_module
from prompt_optimizer.api_client import ChatResult
from src.application.prompt_gate.gate_run_use_cases import (
    GateCase,
    StartGateRunUseCase,
)
from src.domain.bot.entity import Bot
from src.domain.bot.repository import BotRepository
from src.domain.bot.value_objects import BotId
from src.domain.prompt_gate.config_snapshot import take_snapshot
from src.domain.prompt_gate.entity import (
    STATUS_VALIDATING,
    VERDICT_FAIL,
    BotConfigVersion,
)
from src.domain.prompt_gate.gate_run_entity import (
    RUN_COMPLETED,
    RUN_QUEUED,
    PromptGateRun,
)
from src.domain.prompt_gate.gate_run_repository import PromptGateRunRepository
from src.domain.prompt_gate.repository import BotConfigVersionRepository
from src.domain.tenant.repository import TenantRepository

BOT_ID = "bot-1"
TENANT = "t1"


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_uc_and_ctx():
    bot = Bot(id=BotId(value=BOT_ID), tenant_id=TENANT, name="b")
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
    uc = StartGateRunUseCase(
        bot_repository=AsyncMock(spec=BotRepository),
        tenant_repository=AsyncMock(spec=TenantRepository),
        version_repository=version_repo,
        gate_run_repository=gate_repo,
        eval_dataset_repository=AsyncMock(),
        gate_run_repo_factory=lambda: gate_repo,
        version_repo_factory=lambda: version_repo,
    )
    return uc, run, version


def _bg_kwargs(version, cases, *, repeats=2, budget_usd=10.0):
    return {
        "run_id": "run-1", "tenant_id": TENANT, "bot_id": BOT_ID,
        "version_id": "ver-1",
        "config_snapshot": version.config_snapshot,
        "cases": cases, "repeats": repeats, "soft_threshold": 0.8,
        "budget_usd": budget_usd, "api_token": "jwt",
    }


def _case(case_id="d:c1", priority="P0"):
    return GateCase(
        case_id=case_id, question="q", priority=priority,
        assertions=[{
            "type": "contains_all", "params": {"keywords": ["正常"]},
        }],
    )


class _CountingClient:
    """通過 contains_all 的假 client，計呼叫數；每次呼叫成本 0.001。"""

    calls = 0

    def __init__(self, *args, **kwargs):
        pass

    async def chat(self, **kwargs):
        type(self).calls += 1
        return ChatResult(
            answer="正常回答內容", conversation_id="c", tool_calls=[],
            sources=[], usage={
                "estimated_cost": 0.001, "input_tokens": 100,
                "output_tokens": 50, "total_tokens": 150,
            },
            latency_ms=10, trace_id="tr", trace_nodes=[],
        )

    async def close(self):
        pass


def test_budget_exceeded_aborts_remaining_rounds(monkeypatch):
    monkeypatch.setattr(api_client_module, "AgentAPIClient", _CountingClient)
    _CountingClient.calls = 0
    uc, run, version = _make_uc_and_ctx()
    # 單次成本 0.001 > budget 0.0005 → 第一題後即中止
    _run(uc._execute_background(**_bg_kwargs(
        version, [_case()], repeats=5, budget_usd=0.0005,
    )))
    assert run.status == RUN_COMPLETED
    assert run.details["aborted"] is True
    # Round 1 跑完（1 題），Round 2..5 因中止不再打 API
    assert _CountingClient.calls == 1


def test_api_error_marks_case_failed_not_background_error(monkeypatch):
    class _ChatBoom(_CountingClient):
        async def chat(self, **kwargs):
            raise RuntimeError("LLM timeout")

    monkeypatch.setattr(api_client_module, "AgentAPIClient", _ChatBoom)
    uc, run, version = _make_uc_and_ctx()
    _run(uc._execute_background(**_bg_kwargs(
        version, [_case()], repeats=1,
    )))
    # chat 例外 → 空 ChatResult + api_error 硬斷言 → verdict FAIL；
    # run 正常 completed（可看報告），不是 background_error
    assert run.status == RUN_COMPLETED
    assert run.verdict == VERDICT_FAIL


def test_round_two_only_reruns_p0(monkeypatch):
    monkeypatch.setattr(api_client_module, "AgentAPIClient", _CountingClient)
    _CountingClient.calls = 0
    uc, run, version = _make_uc_and_ctx()
    cases = [_case("d:p0", "P0"), _case("d:p1", "P1")]
    _run(uc._execute_background(**_bg_kwargs(version, cases, repeats=2)))
    assert run.status == RUN_COMPLETED
    # Round 1：P0+P1（2 次）；Round 2：只 P0（1 次）→ 共 3 次而非 4 次
    assert _CountingClient.calls == 3
