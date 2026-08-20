"""閘門三層開關與前置條件 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.bot.update_bot_use_case import (
    UpdateBotCommand,
    UpdateBotUseCase,
)
from src.application.prompt_gate.gate_run_use_cases import (
    GatePreconditionError,
    StartGateRunUseCase,
)
from src.domain.bot.entity import Bot
from src.domain.bot.repository import BotRepository
from src.domain.bot.value_objects import BotId
from src.domain.eval_dataset.entity import EvalDataset, EvalTestCase
from src.domain.eval_dataset.repository import EvalDatasetRepository
from src.domain.prompt_gate.config_snapshot import take_snapshot
from src.domain.prompt_gate.entity import (
    STATUS_DRAFT,
    STATUS_VALIDATING,
    BotConfigVersion,
)
from src.domain.prompt_gate.gate_run_repository import (
    PromptGateRunRepository,
)
from src.domain.prompt_gate.repository import BotConfigVersionRepository
from src.domain.shared.exceptions import ValidationError
from src.domain.tenant.entity import Tenant
from src.domain.tenant.repository import TenantRepository

scenarios("unit/prompt_gate/gate_settings.feature")

BOT_ID = "bot-1"
TENANT = "t1"
VERSION_ID = "ver-1"


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


def _dataset(*, enabled=True, platform=False, n=1):
    return EvalDataset(
        tenant_id=TENANT,
        bot_id=None if platform else BOT_ID,
        name="ds",
        is_platform_base=platform,
        test_cases=[
            EvalTestCase(
                case_id=f"c{i}", question="q", priority="P0",
                enabled=enabled,
                assertions=[{"type": "response_not_empty"}],
            )
            for i in range(n)
        ],
    )


def _build_uc(
    context,
    *,
    tenant_flag=True,
    gate_mode="block",
    datasets=None,
    platform_datasets=None,
    today_count=0,
    budget=1.0,
):
    bot = Bot(
        id=BotId(value=BOT_ID), tenant_id=TENANT, name="b",
        base_prompt="舊", gate_mode=gate_mode, gate_daily_limit=20,
        gate_budget_usd=budget, gate_repeats=3,
    )
    bot_repo = AsyncMock(spec=BotRepository)
    bot_repo.find_by_id.return_value = bot

    tenant_repo = AsyncMock(spec=TenantRepository)
    tenant_repo.find_by_id.return_value = Tenant(
        name="t", prompt_gate_enabled=tenant_flag
    )

    version = BotConfigVersion(
        id=VERSION_ID, tenant_id=TENANT, bot_id=BOT_ID, version_no=2,
        config_snapshot=take_snapshot(bot), status=STATUS_DRAFT,
        changed_fields=["base_prompt"],
    )
    version_repo = AsyncMock(spec=BotConfigVersionRepository)
    version_repo.find_by_id.return_value = version

    gate_run_repo = AsyncMock(spec=PromptGateRunRepository)
    gate_run_repo.count_today.return_value = today_count

    eval_repo = AsyncMock(spec=EvalDatasetRepository)
    eval_repo.find_by_bot.return_value = datasets or []
    eval_repo.find_platform_base.return_value = platform_datasets or []

    uc = StartGateRunUseCase(
        bot_repository=bot_repo,
        tenant_repository=tenant_repo,
        version_repository=version_repo,
        gate_run_repository=gate_run_repo,
        eval_dataset_repository=eval_repo,
    )
    # 背景執行不在本 feature 範圍：換成 no-op
    uc._execute_background = AsyncMock()
    context["uc"] = uc
    context["version"] = version
    context["bot"] = bot


@given("租戶未開啟 prompt_gate 且 bot gate_mode 為 block 並已綁題集")
def setup_tenant_off(context):
    _build_uc(context, tenant_flag=False, datasets=[_dataset()])


@given("租戶已開啟 prompt_gate 且 bot gate_mode 為 off")
def setup_mode_off(context):
    _build_uc(context, gate_mode="off", datasets=[_dataset()])


@given("租戶已開啟 prompt_gate 且 bot gate_mode 為 block 但未綁任何題集")
def setup_no_dataset(context):
    _build_uc(context, datasets=[])


@given("租戶已開啟 prompt_gate 且 bot 綁的自訂集全部 case 停用")
def setup_all_disabled(context):
    _build_uc(context, datasets=[_dataset(enabled=False)])


@given("租戶已開啟 prompt_gate 且只有平台通用集含啟用案例")
def setup_platform_only(context):
    _build_uc(
        context, datasets=[], platform_datasets=[_dataset(platform=True)]
    )


@given("租戶已開啟 prompt_gate 且 bot 已綁題集且當日已跑 20 次")
def setup_daily_limit(context):
    _build_uc(context, datasets=[_dataset()], today_count=20)


@given("租戶已開啟 prompt_gate 且 bot 已綁題集且估算成本超過預算")
def setup_over_budget(context):
    # 100 個 P0 案例 × 3 輪 × ~0.01/call 遠超過 0.0001 預算
    _build_uc(context, datasets=[_dataset(n=100)], budget=0.0001)


@given("租戶已開啟 prompt_gate 且 bot 已綁題集且前置全過")
def setup_all_pass(context):
    _build_uc(context, datasets=[_dataset(n=2)], budget=100.0)


@when("對 draft 版本啟動 gate run")
def start_gate_run(context):
    async def _go():
        return await context["uc"].execute(
            tenant_id=TENANT, bot_id=BOT_ID,
            version_id=VERSION_ID, api_token="jwt",
        )

    try:
        context["run"] = _run(_go())
    except GatePreconditionError as exc:
        context["error"] = exc


@then(parsers.parse("啟動被拒絕且錯誤類型為 {code}"))
def verify_precondition_rejected(context, code):
    err = context["error"]
    assert isinstance(err, GatePreconditionError)
    assert err.code == code, f"預期 {code}，實際 {err.code}"


@then("回傳 run_id 且版本狀態為 validating")
def verify_started(context):
    assert context["run"].id
    assert context["version"].status == STATUS_VALIDATING
    assert context["version"].gate_run_id == context["run"].id


# ─── UpdateBot 前置條件 ───


@given("一個未綁任何題集的 bot")
def update_bot_no_dataset(context):
    bot = Bot(id=BotId(value=BOT_ID), tenant_id=TENANT, name="b")
    bot_repo = AsyncMock(spec=BotRepository)
    bot_repo.find_by_id.return_value = bot
    eval_repo = AsyncMock(spec=EvalDatasetRepository)
    eval_repo.find_by_bot.return_value = []
    context["update_uc"] = UpdateBotUseCase(
        bot_repository=bot_repo, eval_dataset_repository=eval_repo
    )
    context["bot"] = bot


@given("一個已綁題集（含啟用案例）的 bot")
def update_bot_with_dataset(context):
    bot = Bot(id=BotId(value=BOT_ID), tenant_id=TENANT, name="b")
    bot_repo = AsyncMock(spec=BotRepository)
    bot_repo.find_by_id.return_value = bot
    eval_repo = AsyncMock(spec=EvalDatasetRepository)
    eval_repo.find_by_bot.return_value = [_dataset()]
    context["update_uc"] = UpdateBotUseCase(
        bot_repository=bot_repo, eval_dataset_repository=eval_repo
    )
    context["bot"] = bot


@when("透過 UpdateBot 將 gate_mode 改為 block")
def update_gate_mode_block(context):
    with pytest.raises(ValidationError) as exc_info:
        _run(
            context["update_uc"].execute(
                UpdateBotCommand(bot_id=BOT_ID, gate_mode="block")
            )
        )
    context["error"] = exc_info.value


@when("透過 UpdateBot 將 gate_mode 改為 warn")
def update_gate_mode_warn(context):
    _run(
        context["update_uc"].execute(
            UpdateBotCommand(bot_id=BOT_ID, gate_mode="warn")
        )
    )


@then('更新被拒絕且錯誤訊息含 "須先設定問題集"')
def verify_update_rejected(context):
    assert "須先設定問題集" in str(context["error"])


@then("更新成功且 gate_mode 為 warn")
def verify_update_ok(context):
    assert context["bot"].gate_mode == "warn"
