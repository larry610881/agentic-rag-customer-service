"""Optimizer × 版本狀態機整合 BDD Step Definitions（Phase D）"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from prompt_optimizer.api_client import ChatResult
from prompt_optimizer.runner import KarpathyLoopRunner
from src.application.eval_dataset.run_use_cases import (
    GetRunUseCase,
    RollbackRunUseCase,
    StartRunUseCase,
    _ShadowAPIClient,
)
from src.application.prompt_gate.version_use_cases import (
    CreateConfigVersionUseCase,
    PublishConfigVersionUseCase,
)
from src.domain.bot.entity import Bot
from src.domain.bot.repository import BotRepository
from src.domain.bot.value_objects import BotId
from src.domain.eval_dataset.repository import (
    EvalDatasetRepository,
)
from src.domain.prompt_gate.entity import (
    SOURCE_OPTIMIZER,
    STATUS_DRAFT,
    STATUS_PUBLISHED,
)
from src.domain.prompt_gate.repository import BotConfigVersionRepository
from src.domain.shared.exceptions import EntityNotFoundError
from src.domain.tenant.entity import Tenant
from src.domain.tenant.repository import TenantRepository

scenarios("unit/eval_dataset/optimizer_gate_handoff.feature")

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


def _chat_result(answer="回答"):
    return ChatResult(
        answer=answer, conversation_id="c-1", tool_calls=[], sources=[],
        usage={"total_tokens": 100, "estimated_cost": 0.001},
    )


class _RecordingClient:
    def __init__(self):
        self.calls: list[dict] = []

    async def chat(self, **kwargs):
        self.calls.append(kwargs)
        return _chat_result()

    async def close(self):
        pass


# ─── 影子 client ───


@given('一個 target_field 為 base_prompt 的影子 client 與候選 prompt "候選 A"')
def shadow_client(context):
    inner = _RecordingClient()
    store = {"base_prompt": "候選 A"}
    context["inner"] = inner
    context["store"] = store
    context["shadow"] = _ShadowAPIClient(
        inner, target_field="base_prompt", prompt_store=store
    )


@when("透過影子 client 發送測試問題")
def shadow_chat(context):
    _run(context["shadow"].chat(message="測試", bot_id=BOT_ID))


@when("候選 prompt 更新為 \"候選 B\" 後再發送測試問題")
def shadow_chat_updated(context):
    context["store"]["base_prompt"] = "候選 B"
    _run(context["shadow"].chat(message="測試", bot_id=BOT_ID))


@then("底層 chat 收到 config_override 含 \"候選 A\" 且 test_mode 為 true")
def verify_shadow_call(context):
    call = context["inner"].calls[-1]
    assert call["config_override"] == {"base_prompt": "候選 A"}
    assert call["test_mode"] is True


@then("底層 chat 收到 config_override 含 \"候選 B\"")
def verify_shadow_updated(context):
    call = context["inner"].calls[-1]
    assert call["config_override"] == {"base_prompt": "候選 B"}


# ─── runner history_override ───


def _dataset_with_history():
    tc = SimpleNamespace(
        id="c1", question="正式問題", priority="P0", category="",
        conversation_history=[
            {"role": "user", "content": "第一句"},
            {"role": "assistant", "content": "第一答"},
        ],
        assertions=[],
    )
    return SimpleNamespace(
        test_cases=[tc],
        metadata=SimpleNamespace(bot_id=BOT_ID),
    )


def _make_runner(context, use_history_override: bool):
    client = _RecordingClient()
    context["client"] = client
    context["runner"] = KarpathyLoopRunner(
        api_client=client,
        db_read_prompt=lambda t: "",
        db_write_prompt=lambda t, p: None,
        use_history_override=use_history_override,
    )
    context["dataset"] = _dataset_with_history()


@given("一個開啟 history_override 模式的 runner 與含兩則歷史的測試案例")
def runner_with_override(context):
    _make_runner(context, use_history_override=True)


@given("一個關閉 history_override 模式的 runner 與含兩則歷史的測試案例")
def runner_without_override(context):
    _make_runner(context, use_history_override=False)


@when("runner 評估該案例")
def runner_eval(context):
    config = SimpleNamespace(max_iterations=1)
    _run(
        context["runner"]._eval_all(context["dataset"], config)
    )


@then("只發出一次 chat 且帶有兩則 history_override")
def verify_single_chat(context):
    calls = context["client"].calls
    assert len(calls) == 1
    assert len(calls[0]["history_override"]) == 2


@then("發出三次 chat 且未帶 history_override")
def verify_warmup_chats(context):
    calls = context["client"].calls
    assert len(calls) == 3  # 2 warm-up + 1 正式
    assert all("history_override" not in c for c in calls)


# ─── 優化收尾建 draft ───


def _make_start_uc(context, *, factory):
    uc = StartRunUseCase(
        eval_dataset_repository=AsyncMock(spec=EvalDatasetRepository),
        run_manager=AsyncMock(),
        create_version_factory=factory,
    )
    context["start_uc"] = uc


@given("一次 baseline 0.6 最佳 0.9 的優化結果")
def improved_result(context):
    created = []

    def factory():
        uc = AsyncMock(spec=CreateConfigVersionUseCase)

        async def _exec(cmd):
            created.append(cmd)
            return SimpleNamespace(id="ver-new")

        uc.execute.side_effect = _exec
        return uc

    context["created"] = created
    _make_start_uc(context, factory=factory)
    context["kwargs"] = {
        "tenant_id": TENANT, "bot_id": BOT_ID,
        "target_field": "base_prompt",
        "best_prompt": "優化後", "initial_prompt": "原始",
        "improved": True, "run_id": "run-1",
    }


@given("一次 baseline 與最佳同分的優化結果")
def not_improved_result(context):
    created = []

    def factory():
        uc = AsyncMock(spec=CreateConfigVersionUseCase)
        uc.execute.side_effect = lambda cmd: created.append(cmd)
        return uc

    context["created"] = created
    _make_start_uc(context, factory=factory)
    context["kwargs"] = {
        "tenant_id": TENANT, "bot_id": BOT_ID,
        "target_field": "base_prompt",
        "best_prompt": "原始", "initial_prompt": "原始",
        "improved": False, "run_id": "run-1",
    }


@given("一次有進步的優化結果但建版會拋錯")
def failing_factory_result(context):
    def factory():
        uc = AsyncMock(spec=CreateConfigVersionUseCase)
        uc.execute.side_effect = RuntimeError("db down")
        return uc

    context["created"] = []
    _make_start_uc(context, factory=factory)
    context["kwargs"] = {
        "tenant_id": TENANT, "bot_id": BOT_ID,
        "target_field": "base_prompt",
        "best_prompt": "優化後", "initial_prompt": "原始",
        "improved": True, "run_id": "run-1",
    }


@when("執行優化收尾")
def do_finalize(context):
    context["version_id"] = _run(
        context["start_uc"]._create_optimizer_draft(**context["kwargs"])
    )


@then("建立一筆 source 為 optimizer 的 draft 且 source_run_id 為該 run")
def verify_draft_created(context):
    assert context["version_id"] == "ver-new"
    cmd = context["created"][0]
    assert cmd.source == SOURCE_OPTIMIZER
    assert cmd.source_run_id == "run-1"


@then("draft 的變更欄位包含 base_prompt")
def verify_draft_changes(context):
    assert "base_prompt" in context["created"][0].changes


@then("不建立任何版本")
def verify_no_version(context):
    assert context["version_id"] is None
    assert context["created"] == []


@then("收尾正常結束且無例外")
def verify_fail_open(context):
    assert context["version_id"] is None


# ─── rollback 收斂 ───


def _iteration(tenant_id=TENANT):
    return SimpleNamespace(
        iteration=3, tenant_id=tenant_id, bot_id=BOT_ID,
        target_field="base_prompt", prompt_snapshot="歷史 prompt",
        score=0.85,
    )


def _make_rollback(context, *, gate_mode: str, iteration=None):
    it = iteration or _iteration()
    run_repo = AsyncMock()
    run_repo.get_iterations.return_value = [it]

    bot = Bot(
        id=BotId(value=BOT_ID), tenant_id=TENANT, name="b",
        base_prompt="現行 prompt", gate_mode=gate_mode,
    )
    bot_repo = AsyncMock(spec=BotRepository)
    bot_repo.find_by_id.return_value = bot

    tenant_repo = AsyncMock(spec=TenantRepository)
    tenant_repo.find_by_id.return_value = Tenant(
        name="t", prompt_gate_enabled=True
    )

    store: dict = {}

    version_repo = AsyncMock(spec=BotConfigVersionRepository)

    async def _save(v):
        store[v.id] = v

    async def _find(vid, tid):
        v = store.get(vid)
        return v if v and v.tenant_id == tid else None

    async def _create_next(v):
        v.version_no = 5
        store[v.id] = v
        return v

    async def _save_transition(v, *, expected_status, action):
        store[v.id] = v

    version_repo.save.side_effect = _save
    version_repo.find_by_id.side_effect = _find
    version_repo.next_version_no.return_value = 5
    version_repo.create_next_version.side_effect = _create_next
    version_repo.save_status_transition.side_effect = _save_transition

    create_uc = CreateConfigVersionUseCase(bot_repo, version_repo)
    publish_uc = PublishConfigVersionUseCase(
        bot_repository=bot_repo,
        version_repository=version_repo,
        tenant_repository=tenant_repo,
    )
    context["store"] = store
    context["rollback_uc"] = RollbackRunUseCase(
        optimization_run_repository=run_repo,
        bot_repository=bot_repo,
        create_version_use_case=create_uc,
        publish_version_use_case=publish_uc,
    )


@given("一筆歷史 iteration 且 bot gate 未啟用")
def rollback_gate_off(context):
    _make_rollback(context, gate_mode="off")


@given("一筆歷史 iteration 且 bot gate 為 block")
def rollback_gate_block(context):
    _make_rollback(context, gate_mode="block")


@given("一筆屬於其他租戶的歷史 iteration")
def rollback_foreign(context):
    _make_rollback(
        context, gate_mode="off", iteration=_iteration(tenant_id="t-other")
    )
    run_repo = AsyncMock()
    run_repo.get_iterations.return_value = [_iteration(tenant_id="t-other")]
    context["get_uc"] = GetRunUseCase(
        optimization_run_repository=run_repo,
        run_manager=SimpleNamespace(get_run=lambda rid: None),
    )


@when("對該 iteration 執行 rollback")
def do_rollback(context):
    try:
        context["result"] = _run(
            context["rollback_uc"].execute("run-1", 3, tenant_id=TENANT)
        )
    except EntityNotFoundError as exc:
        context["error"] = exc


@when("以本租戶查詢該 run")
def do_get_run(context):
    with pytest.raises(EntityNotFoundError) as exc_info:
        _run(context["get_uc"].execute("run-1", tenant_id=TENANT))
    context["error"] = exc_info.value


@then("建立 source 為 optimizer 的版本並已發布")
def verify_rollback_published(context):
    result = context["result"]
    assert result["applied"] is True
    assert result["published"] is True
    version = context["store"][result["version_id"]]
    assert version.source == SOURCE_OPTIMIZER
    assert version.status == STATUS_PUBLISHED


@then("建立 draft 且回報未發布（需走閘門）")
def verify_rollback_draft_only(context):
    result = context["result"]
    assert result["applied"] is True
    assert result["published"] is False
    assert "閘門" in result["note"]
    version = context["store"][result["version_id"]]
    assert version.status == STATUS_DRAFT


@then("rollback 被拒絕（找不到 run）")
@then("查詢被拒絕（找不到 run）")
def verify_scoped_out(context):
    assert isinstance(context["error"], EntityNotFoundError)
