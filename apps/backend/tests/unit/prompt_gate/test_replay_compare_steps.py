"""真實流量回放 pairwise 對比 BDD Step Definitions（Phase G）"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

import src.application.prompt_gate.replay_use_cases as replay_module
from prompt_optimizer.api_client import ChatResult
from src.application.prompt_gate.gate_run_use_cases import (
    GatePreconditionError,
)
from src.application.prompt_gate.replay_use_cases import (
    StartReplayCompareUseCase,
)
from src.domain.bot.entity import Bot
from src.domain.bot.repository import BotRepository
from src.domain.bot.value_objects import BotId
from src.domain.conversation.repository import ConversationRepository
from src.domain.prompt_gate.config_snapshot import take_snapshot
from src.domain.prompt_gate.entity import (
    STATUS_DRAFT,
    STATUS_PUBLISHED,
    BotConfigVersion,
)
from src.domain.prompt_gate.gate_run_entity import (
    RUN_COMPLETED,
    RUN_QUEUED,
    PromptGateRun,
)
from src.domain.prompt_gate.gate_run_repository import (
    PromptGateRunRepository,
)
from src.domain.prompt_gate.replay import (
    aggregate_replay,
    consistent_verdict,
)
from src.domain.prompt_gate.repository import BotConfigVersionRepository

scenarios("unit/prompt_gate/replay_compare.feature")

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


# ─── 換位判定 ───


@when(parsers.parse('正序判定為 "{normal}" 且換位判定為 "{swapped}"'))
def do_verdict(context, normal, swapped):
    context["verdict"] = consistent_verdict(normal, swapped)


@then(parsers.parse("該題結果為 {expected}"))
def verify_verdict(context, expected):
    assert context["verdict"] == expected


# ─── 聚合 ───


@given(parsers.parse("逐題結果為 {results}"))
def set_results(context, results):
    context["results"] = [r.strip() for r in results.split(",")]


@when("聚合回放結果")
def do_aggregate(context):
    context["summary"] = aggregate_replay(context["results"])


@then("統計為 candidate 2 勝 baseline 1 勝 1 平且勝率 0.5")
def verify_summary(context):
    s = context["summary"]
    assert (s.candidate_wins, s.baseline_wins, s.ties) == (2, 1, 1)
    assert s.win_rate == 0.5


# ─── use case 前置與背景 ───


def _build_uc(context, *, questions, today_count=0, judge_raises=False):
    bot = Bot(
        id=BotId(value=BOT_ID), tenant_id=TENANT, name="b",
        base_prompt="線上", gate_daily_limit=20, gate_budget_usd=100.0,
    )
    bot_repo = AsyncMock(spec=BotRepository)
    bot_repo.find_by_id.return_value = bot

    current = BotConfigVersion(
        id="ver-cur", tenant_id=TENANT, bot_id=BOT_ID, version_no=1,
        config_snapshot=take_snapshot(bot), status=STATUS_PUBLISHED,
        is_current=True,
    )
    cand_bot = Bot(
        id=BotId(value=BOT_ID), tenant_id=TENANT, name="b",
        base_prompt="候選",
    )
    candidate = BotConfigVersion(
        id="ver-cand", tenant_id=TENANT, bot_id=BOT_ID, version_no=2,
        config_snapshot=take_snapshot(cand_bot), status=STATUS_DRAFT,
    )
    version_repo = AsyncMock(spec=BotConfigVersionRepository)
    version_repo.find_by_id.return_value = candidate
    version_repo.find_current.return_value = current

    run_store: dict[str, PromptGateRun] = {}
    gate_repo = AsyncMock(spec=PromptGateRunRepository)
    gate_repo.count_today.return_value = today_count

    async def _save(r):
        run_store[r.id] = r

    async def _find(rid, tid):
        return run_store.get(rid)

    gate_repo.save.side_effect = _save
    gate_repo.find_by_id.side_effect = _find

    conv_repo = AsyncMock(spec=ConversationRepository)
    conv_repo.find_recent_user_questions.return_value = questions

    uc = StartReplayCompareUseCase(
        bot_repository=bot_repo,
        version_repository=version_repo,
        gate_run_repository=gate_repo,
        conversation_repository=conv_repo,
        gate_run_repo_factory=lambda: gate_repo,
    )
    context.update(uc=uc, run_store=run_store, candidate=candidate)
    context["judge_raises"] = judge_raises


class _FakeClient:
    def __init__(self, *a, **k):
        pass

    async def chat(self, message, bot_id=None, config_override=None, **kw):
        # 依 override 回不同答案，讓 judge 有得比
        flavor = (config_override or {}).get("base_prompt", "線上")
        return ChatResult(
            answer=f"[{flavor}] 回答：{message}",
            conversation_id="c", tool_calls=[], sources=[],
            usage={"estimated_cost": 0.001},
        )

    async def close(self):
        pass


@given("一個沒有任何歷史使用者訊息的 bot")
def bot_no_history(context):
    _build_uc(context, questions=[])


@given("一個當日已達 gate_daily_limit 的 bot")
def bot_at_limit(context):
    _build_uc(context, questions=["q1"], today_count=20)


@given("一個有兩則歷史問題的 bot 與 candidate 版本")
def bot_with_history(context):
    _build_uc(context, questions=["問題一", "問題二"])


@given("一個有兩則歷史問題的 bot 且 judge 會拋錯")
def bot_with_failing_judge(context):
    _build_uc(context, questions=["問題一", "問題二"], judge_raises=True)


@when("啟動回放對比")
def start_replay(context):
    with pytest.raises(GatePreconditionError) as exc_info:
        _run(
            context["uc"].execute(
                tenant_id=TENANT, bot_id=BOT_ID,
                version_id="ver-cand", api_token="jwt",
            )
        )
    context["error"] = exc_info.value


@when("執行回放對比背景任務")
def run_background(context, monkeypatch):
    import prompt_optimizer.api_client as api_module

    monkeypatch.setattr(api_module, "AgentAPIClient", _FakeClient)

    if context["judge_raises"]:
        async def _boom(self, q, a, b):
            raise RuntimeError("judge down")

        monkeypatch.setattr(
            replay_module.PairwiseJudge, "judge", _boom
        )
    else:
        # candidate（含「候選」字樣）永遠較佳：正序回 2、換位回 1
        async def _judge(self, q, a, b):
            return "2" if "候選" in b else "1"

        monkeypatch.setattr(
            replay_module.PairwiseJudge, "judge", _judge
        )

    run = PromptGateRun(
        id="run-1", tenant_id=TENANT, bot_id=BOT_ID,
        version_id="ver-cand", status=RUN_QUEUED,
        details={"type": "replay_compare"},
    )
    context["run_store"]["run-1"] = run
    _run(
        context["uc"]._execute_background(
            run_id="run-1", tenant_id=TENANT, bot_id=BOT_ID,
            baseline_snapshot={"base_prompt": "線上"},
            candidate_snapshot={"base_prompt": "候選"},
            questions=["問題一", "問題二"],
            budget_usd=100.0, api_token="jwt", judge_api_key="",
        )
    )
    context["run"] = context["run_store"]["run-1"]


@then(parsers.parse("啟動被拒絕且錯誤類型為 {code}"))
def verify_precondition(context, code):
    assert isinstance(context["error"], GatePreconditionError)
    assert context["error"].code == code


@then("run 完成且 details 型別為 replay_compare")
def verify_run_completed(context):
    run = context["run"]
    assert run.status == RUN_COMPLETED
    assert run.details["type"] == "replay_compare"


@then("每題含 baseline 與 candidate 的回應與判定")
def verify_items(context):
    items = context["run"].details["items"]
    assert len(items) == 2
    for item in items:
        assert "[線上]" in item["baseline_answer"]
        assert "[候選]" in item["candidate_answer"]
        assert item["verdict"] == "candidate"
    assert context["run"].details["summary"]["candidate_wins"] == 2


@then("run 完成且全部題目判定為 tie")
def verify_all_tie(context):
    run = context["run"]
    assert run.status == RUN_COMPLETED
    assert all(i["verdict"] == "tie" for i in run.details["items"])
    assert run.details["summary"]["ties"] == 2
