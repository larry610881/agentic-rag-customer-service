"""Regression: 優化迴圈中途例外仍把線上 prompt 回寫為 best（M34）。"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from prompt_optimizer.api_client import ChatResult
from prompt_optimizer.config import PromptTarget
from prompt_optimizer.dataset import Assertion, CostConfigData, Dataset
from prompt_optimizer.dataset import DatasetMetadata, TestCase
from prompt_optimizer.runner import KarpathyLoopRunner


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _dataset():
    return Dataset(
        metadata=DatasetMetadata(
            tenant_id="t1", bot_id="b1", target_prompt="base_prompt",
            agent_mode="react",
            cost_config=CostConfigData(),
        ),
        default_assertions=(),
        test_cases=(
            TestCase(id="c1", question="q", priority="P1",
                     assertions=(Assertion(type="not_empty", params={}),)),
        ),
    )


def test_write_prompt_restores_best_when_mutate_raises():
    writes: list = []
    api = AsyncMock()
    api.chat = AsyncMock(return_value=ChatResult(
        answer="baseline answer", conversation_id="", tool_calls=[],
        sources=[], usage=None, latency_ms=1,
    ))
    mutator = MagicMock()
    mutator.mutate = AsyncMock(side_effect=RuntimeError("rate limit"))

    runner = KarpathyLoopRunner(
        api_client=api,
        db_read_prompt=lambda target: "BASELINE_PROMPT",
        db_write_prompt=lambda target, prompt: writes.append(prompt),
        evaluator=None,
        mutator=mutator,
    )
    from prompt_optimizer.config import OptimizationConfig

    cfg = OptimizationConfig(
        target=PromptTarget(
            level="bot", field="base_prompt", bot_id="b1", tenant_id="t1"
        ),
        max_iterations=3, patience=2, budget=200,
    )
    with pytest.raises(RuntimeError):
        _run(runner.run(cfg, _dataset()))

    # finally 一律回寫 best（baseline），不留在 discarded 候選
    assert writes, "例外時未回寫 prompt"
    assert writes[-1] == "BASELINE_PROMPT"
