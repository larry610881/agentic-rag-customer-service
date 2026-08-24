"""Regression: validate 遇大量 API 失敗整輪作廢，不記假 FAIL（M28）。

驗證跑到一半 JWT 過期或後端 5xx → 每題 API 呼叫拋例外。若照舊塞 answer="" 的
ChatResult，assertions 全掛、該輪記 0 分 → verdict=FAIL 連同 unstable/p0 寫進 run
歷史，與真實品質失敗無法區分。修法：失敗率超閾值時拋 EvalInfrastructureError（→502），
且不落任何歷史。
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.application.eval_dataset.eval_use_cases import (
    EvalInfrastructureError,
    RunValidationCommand,
    RunValidationEvalUseCase,
)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _fake_dataset(tenant_id: str):
    case = SimpleNamespace(
        case_id="c1", question="q1", priority="P0", category="general",
        assertions=[{"type": "not_empty", "params": {}}],
        conversation_history=[],
    )
    return SimpleNamespace(
        id=SimpleNamespace(value="ds-1"),
        tenant_id=tenant_id,
        is_platform_base=False,
        bot_id="b1",
        target_prompt="base_prompt",
        description="d",
        default_assertions=[],
        test_cases=[case],
        cost_config={},
    )


def test_validate_aborts_and_persists_nothing_on_api_failures(monkeypatch):
    class _FailingClient:
        def __init__(self, **_kw):
            pass

        async def chat(self, **_kw):
            raise RuntimeError("401 Unauthorized")

        async def close(self):
            pass

    import prompt_optimizer.api_client as api_mod
    monkeypatch.setattr(api_mod, "AgentAPIClient", _FailingClient)

    dataset_repo = AsyncMock()
    dataset_repo.find_by_id.return_value = _fake_dataset("t1")
    run_repo = AsyncMock()

    uc = RunValidationEvalUseCase(
        eval_dataset_repository=dataset_repo,
        optimization_run_repository=run_repo,
    )
    command = RunValidationCommand(
        tenant_id="t1", dataset_id="ds-1", api_token="tok",
        repeats=1, bot_id="b1", role="tenant_admin",
    )

    with pytest.raises(EvalInfrastructureError):
        _run(uc.execute(command))

    # 關鍵：整輪作廢，沒有任何假 FAIL 被寫進歷史
    run_repo.save_iteration.assert_not_called()
