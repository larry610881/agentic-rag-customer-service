"""整合測試：send_message_use_case 組裝 tool_rag_params 的邏輯。"""
from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.agent.send_message_use_case import (
    build_tool_rag_params_map,
)
from src.domain.bot.entity import Bot, BotLLMParams, ToolRagConfig
from src.domain.bot.worker_config import WorkerConfig

scenarios("unit/agent/per_tool_rag_dispatch.feature")


@pytest.fixture
def context() -> dict:
    return {}


@given(parsers.parse(
    "Bot 全域 rag_top_k={top_k:d} rag_score_threshold={threshold:f}"
))
def bot_global(context, top_k: int, threshold: float) -> None:
    context["bot"] = Bot(
        llm_params=BotLLMParams(rag_top_k=top_k, rag_score_threshold=threshold),
        enabled_tools=["rag_query", "query_dm_with_image"],
    )


@given(parsers.parse('Bot 的 "{tool_name}" 工具覆蓋 top_k={top_k:d}'))
def bot_tool_override(context, tool_name: str, top_k: int) -> None:
    bot: Bot = context["bot"]
    bot.tool_configs[tool_name] = ToolRagConfig(rag_top_k=top_k)


@given("Bot 沒有任何 per-tool 設定")
def bot_no_overrides(context) -> None:
    context["bot"].tool_configs = {}


@given(parsers.parse('Worker 的 "{tool_name}" 工具覆蓋 top_k={top_k:d}'))
def worker_tool_override(context, tool_name: str, top_k: int) -> None:
    worker: WorkerConfig = context.setdefault("worker", WorkerConfig())
    worker.tool_configs[tool_name] = ToolRagConfig(rag_top_k=top_k)


@when("為這個 Bot 組裝工具參數 (tool_rag_params)")
def build_for_bot(context) -> None:
    context["tool_rag_params"] = build_tool_rag_params_map(
        bot=context["bot"], worker=None,
    )


@when("為這個 Worker 組裝工具參數 (tool_rag_params)")
def build_for_worker(context) -> None:
    context["tool_rag_params"] = build_tool_rag_params_map(
        bot=context["bot"], worker=context.get("worker"),
    )


@then(parsers.parse('"{tool_name}" 的 rag_top_k 應為 {expected:d}'))
def assert_top_k(context, tool_name: str, expected: int) -> None:
    assert context["tool_rag_params"][tool_name]["rag_top_k"] == expected


@then("兩個工具的 rag_score_threshold 應都為 0.3")
def assert_thresholds(context) -> None:
    params = context["tool_rag_params"]
    assert params["rag_query"]["rag_score_threshold"] == pytest.approx(0.3)
    assert params["query_dm_with_image"]["rag_score_threshold"] == pytest.approx(0.3)
