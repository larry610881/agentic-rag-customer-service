"""Per-tool RAG config BDD step definitions."""
from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.domain.bot.entity import Bot, BotLLMParams, ToolRagConfig
from src.domain.bot.tool_rag_resolver import resolve_tool_rag_params
from src.domain.bot.worker_config import WorkerConfig

scenarios("unit/bot/per_tool_rag_config.feature")


@pytest.fixture
def context() -> dict:
    return {}


# ── Given ───────────────────────────────────────────────────────────

@given(parsers.parse("一個 Bot 預設 rag_top_k={top_k:d} 且 rag_score_threshold={threshold:f}"))
def bot_with_defaults(context, top_k: int, threshold: float) -> None:
    context["bot"] = Bot(
        llm_params=BotLLMParams(rag_top_k=top_k, rag_score_threshold=threshold),
    )


@given(parsers.parse("一個 Bot 預設 rag_top_k={top_k:d} rag_score_threshold={threshold:f}"))
def bot_with_top_k_and_threshold(context, top_k: int, threshold: float) -> None:
    context["bot"] = Bot(
        llm_params=BotLLMParams(rag_top_k=top_k, rag_score_threshold=threshold),
    )


@given(parsers.parse(
    "一個 Bot 預設 rag_top_k={top_k:d} rag_score_threshold={threshold:f} "
    "rerank_enabled={rerank_enabled}"
))
def bot_with_rerank_defaults(
    context, top_k: int, threshold: float, rerank_enabled: str
) -> None:
    context["bot"] = Bot(
        llm_params=BotLLMParams(rag_top_k=top_k, rag_score_threshold=threshold),
        rerank_enabled=(rerank_enabled == "True"),
    )


@given(parsers.parse(
    '一個 Bot 全域 rerank_enabled={rerank_enabled} '
    'rerank_model="{rerank_model}" rerank_top_n={rerank_top_n:d}'
))
def bot_with_rerank_full(
    context, rerank_enabled: str, rerank_model: str, rerank_top_n: int
) -> None:
    context["bot"] = Bot(
        llm_params=BotLLMParams(),
        rerank_enabled=(rerank_enabled == "True"),
        rerank_model=rerank_model,
        rerank_top_n=rerank_top_n,
    )


@given(parsers.parse('Bot 沒有 "{tool_name}" 的 per-tool 設定'))
def bot_without_tool_config(context, tool_name: str) -> None:
    bot: Bot = context["bot"]
    bot.tool_configs.pop(tool_name, None)


@given(parsers.parse('Bot 的 "{tool_name}" 工具設定 top_k={top_k:d}'))
def bot_tool_top_k(context, tool_name: str, top_k: int) -> None:
    bot: Bot = context["bot"]
    existing = bot.tool_configs.get(tool_name, ToolRagConfig())
    bot.tool_configs[tool_name] = ToolRagConfig(
        rag_top_k=top_k,
        rag_score_threshold=existing.rag_score_threshold,
        rerank_enabled=existing.rerank_enabled,
        rerank_model=existing.rerank_model,
        rerank_top_n=existing.rerank_top_n,
    )


@given(parsers.parse('Bot 的 "{tool_name}" 工具設定 rerank_enabled={rerank_enabled}'))
def bot_tool_rerank(context, tool_name: str, rerank_enabled: str) -> None:
    bot: Bot = context["bot"]
    existing = bot.tool_configs.get(tool_name, ToolRagConfig())
    bot.tool_configs[tool_name] = ToolRagConfig(
        rag_top_k=existing.rag_top_k,
        rag_score_threshold=existing.rag_score_threshold,
        rerank_enabled=(rerank_enabled == "True"),
        rerank_model=existing.rerank_model,
        rerank_top_n=existing.rerank_top_n,
    )


@given(parsers.parse('Worker 的 "{tool_name}" 工具設定 top_k={top_k:d}'))
def worker_tool_top_k(context, tool_name: str, top_k: int) -> None:
    worker: WorkerConfig = context.setdefault("worker", WorkerConfig())
    existing = worker.tool_configs.get(tool_name, ToolRagConfig())
    worker.tool_configs[tool_name] = ToolRagConfig(
        rag_top_k=top_k,
        rag_score_threshold=existing.rag_score_threshold,
        rerank_enabled=existing.rerank_enabled,
        rerank_model=existing.rerank_model,
        rerank_top_n=existing.rerank_top_n,
    )


@given(parsers.parse('Worker 沒有 "{tool_name}" 的 per-tool 設定'))
def worker_without_tool(context, tool_name: str) -> None:
    worker: WorkerConfig = context.setdefault("worker", WorkerConfig())
    worker.tool_configs.pop(tool_name, None)


# ── When ────────────────────────────────────────────────────────────

@when("建立一個空的 ToolRagConfig")
def create_empty_tool_rag_config(context) -> None:
    context["tool_rag_config"] = ToolRagConfig()


@when(parsers.parse('為 Bot 的 "{tool_name}" 工具設定 top_k={top_k:d}'))
def set_bot_tool_top_k(context, tool_name: str, top_k: int) -> None:
    bot: Bot = context["bot"]
    bot.tool_configs[tool_name] = ToolRagConfig(rag_top_k=top_k)


@when(parsers.parse('解析 "{tool_name}" 的最終 RAG 參數'))
def resolve_bot_tool(context, tool_name: str) -> None:
    bot: Bot = context["bot"]
    context["resolved"] = resolve_tool_rag_params(
        tool_name=tool_name, bot=bot, worker=None,
    )


@when(parsers.parse('解析 Worker 下 "{tool_name}" 的最終 RAG 參數'))
def resolve_worker_tool(context, tool_name: str) -> None:
    bot: Bot = context["bot"]
    worker: WorkerConfig | None = context.get("worker")
    context["resolved"] = resolve_tool_rag_params(
        tool_name=tool_name, bot=bot, worker=worker,
    )


# ── Then ────────────────────────────────────────────────────────────

@then("所有欄位應為 None")
def all_none(context) -> None:
    cfg: ToolRagConfig = context["tool_rag_config"]
    assert cfg.rag_top_k is None
    assert cfg.rag_score_threshold is None
    assert cfg.rerank_enabled is None
    assert cfg.rerank_model is None
    assert cfg.rerank_top_n is None


@then(parsers.parse('Bot 的 tool_configs 中 "{tool_name}" 的 rag_top_k 應為 {expected:d}'))
def assert_bot_tool_top_k(context, tool_name: str, expected: int) -> None:
    bot: Bot = context["bot"]
    assert bot.tool_configs[tool_name].rag_top_k == expected


@then(parsers.parse('Bot 的 tool_configs 中 "{tool_name}" 的 rag_score_threshold 應為 None'))
def assert_bot_tool_threshold_none(context, tool_name: str) -> None:
    bot: Bot = context["bot"]
    assert bot.tool_configs[tool_name].rag_score_threshold is None


@then(parsers.parse("rag_top_k 應為 {expected:d}"))
def assert_resolved_top_k(context, expected: int) -> None:
    assert context["resolved"]["rag_top_k"] == expected


@then(parsers.parse("rag_score_threshold 應為 {expected:f}"))
def assert_resolved_threshold(context, expected: float) -> None:
    assert context["resolved"]["rag_score_threshold"] == pytest.approx(expected)


@then(parsers.parse("rerank_enabled 應為 {expected}"))
def assert_resolved_rerank_enabled(context, expected: str) -> None:
    assert context["resolved"]["rerank_enabled"] == (expected == "True")


@then(parsers.parse('rerank_model 應為 "{expected}"'))
def assert_resolved_rerank_model(context, expected: str) -> None:
    assert context["resolved"]["rerank_model"] == expected


@then(parsers.parse("rerank_top_n 應為 {expected:d}"))
def assert_resolved_rerank_top_n(context, expected: int) -> None:
    assert context["resolved"]["rerank_top_n"] == expected
