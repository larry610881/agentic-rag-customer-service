"""Regression: replay PairwiseJudge 的 token 用量被記帳（H5）。"""

import asyncio
import sys
import types
from unittest.mock import AsyncMock, MagicMock

from src.application.prompt_gate.replay_use_cases import PairwiseJudge


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _patch_chat_openai(monkeypatch, *, usage_metadata):
    """把 langchain_openai.ChatOpenAI 換成回傳固定 usage 的 fake。"""
    response = MagicMock()
    response.content = "回答一"
    response.usage_metadata = usage_metadata
    response.response_metadata = {"model_name": "gpt-4o-mini"}

    fake_llm = MagicMock()
    fake_llm.ainvoke = AsyncMock(return_value=response)

    fake_module = types.ModuleType("langchain_openai")
    fake_module.ChatOpenAI = MagicMock(return_value=fake_llm)
    monkeypatch.setitem(sys.modules, "langchain_openai", fake_module)


def test_judge_records_usage_via_callback(monkeypatch):
    _patch_chat_openai(
        monkeypatch,
        usage_metadata={"input_tokens": 120, "output_tokens": 8},
    )
    recorded = []

    async def _on_usage(model, meta):
        recorded.append((model, meta))

    judge = PairwiseJudge(api_key="k", on_usage=_on_usage)
    verdict = _run(judge.judge("問題", "答A", "答B"))

    assert verdict == "回答一"
    assert len(recorded) == 1
    model, meta = recorded[0]
    assert model == "gpt-4o-mini"
    assert meta["input_tokens"] == 120
    assert meta["output_tokens"] == 8


def test_judge_no_callback_is_safe(monkeypatch):
    _patch_chat_openai(
        monkeypatch, usage_metadata={"input_tokens": 5, "output_tokens": 1}
    )
    judge = PairwiseJudge(api_key="k")  # on_usage=None
    assert _run(judge.judge("q", "a", "b")) == "回答一"  # 不崩潰


def test_judge_no_usage_metadata_skips_callback(monkeypatch):
    _patch_chat_openai(monkeypatch, usage_metadata=None)
    recorded = []

    async def _on_usage(model, meta):
        recorded.append((model, meta))

    judge = PairwiseJudge(api_key="k", on_usage=_on_usage)
    _run(judge.judge("q", "a", "b"))
    assert recorded == []  # 無 usage → 不呼叫
