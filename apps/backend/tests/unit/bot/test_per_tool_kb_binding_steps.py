"""Per-tool KB binding (kb_ids) BDD step definitions.

繼承優先序：Worker per-tool kb_ids > Bot per-tool kb_ids > Bot 全域 (None)
"""
from __future__ import annotations

import ast

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.domain.bot.entity import Bot, BotLLMParams, ToolRagConfig
from src.domain.bot.tool_rag_resolver import resolve_tool_rag_params
from src.domain.bot.worker_config import WorkerConfig

scenarios("unit/bot/per_tool_kb_binding.feature")


@pytest.fixture
def context() -> dict:
    return {}


def _parse_kb_list(raw: str) -> list[str]:
    """解析 feature 內 ["a", "b"] 格式為 list[str]。"""
    return list(ast.literal_eval(raw))


# ── Given ───────────────────────────────────────────────────────────


@given(parsers.parse("一個 Bot 全域綁定 KB {kb_list}"))
def bot_with_global_kbs(context, kb_list: str) -> None:
    context["bot"] = Bot(
        llm_params=BotLLMParams(),
        knowledge_base_ids=_parse_kb_list(kb_list),
    )


@given(parsers.parse('Bot 沒有 "{tool_name}" 的 per-tool 設定'))
def bot_without_tool_config(context, tool_name: str) -> None:
    bot: Bot = context["bot"]
    bot.tool_configs.pop(tool_name, None)


@given(parsers.parse('Bot 的 "{tool_name}" 工具設定 kb_ids={kb_list}'))
def bot_tool_kb_ids(context, tool_name: str, kb_list: str) -> None:
    bot: Bot = context["bot"]
    existing = bot.tool_configs.get(tool_name, ToolRagConfig())
    bot.tool_configs[tool_name] = ToolRagConfig(
        rag_top_k=existing.rag_top_k,
        rag_score_threshold=existing.rag_score_threshold,
        rerank_enabled=existing.rerank_enabled,
        rerank_model=existing.rerank_model,
        rerank_top_n=existing.rerank_top_n,
        kb_ids=_parse_kb_list(kb_list),
    )


@given(parsers.parse('Worker 的 "{tool_name}" 工具設定 kb_ids={kb_list}'))
def worker_tool_kb_ids(context, tool_name: str, kb_list: str) -> None:
    worker: WorkerConfig = context.setdefault("worker", WorkerConfig())
    existing = worker.tool_configs.get(tool_name, ToolRagConfig())
    worker.tool_configs[tool_name] = ToolRagConfig(
        rag_top_k=existing.rag_top_k,
        rag_score_threshold=existing.rag_score_threshold,
        rerank_enabled=existing.rerank_enabled,
        rerank_model=existing.rerank_model,
        rerank_top_n=existing.rerank_top_n,
        kb_ids=_parse_kb_list(kb_list),
    )


# ── When ────────────────────────────────────────────────────────────


@when("建立一個空的 ToolRagConfig")
def create_empty_tool_rag_config(context) -> None:
    context["tool_rag_config"] = ToolRagConfig()


@when(parsers.parse('解析 "{tool_name}" 的最終 kb_ids'))
def resolve_bot_tool_kb_ids(context, tool_name: str) -> None:
    bot: Bot = context["bot"]
    context["resolved"] = resolve_tool_rag_params(
        tool_name=tool_name, bot=bot, worker=None,
    )


@when(parsers.parse('解析 Worker 下 "{tool_name}" 的最終 kb_ids'))
def resolve_worker_tool_kb_ids(context, tool_name: str) -> None:
    bot: Bot = context["bot"]
    worker: WorkerConfig | None = context.get("worker")
    context["resolved"] = resolve_tool_rag_params(
        tool_name=tool_name, bot=bot, worker=worker,
    )


# ── Then ────────────────────────────────────────────────────────────


@then("kb_ids 應為 None")
def assert_resolved_kb_ids_none(context) -> None:
    assert context["resolved"]["kb_ids"] is None


@then(parsers.re(r"kb_ids 應為 (?P<kb_list>\[.*\])"))
def assert_resolved_kb_ids(context, kb_list: str) -> None:
    expected = _parse_kb_list(kb_list)
    assert context["resolved"]["kb_ids"] == expected


@then("kb_ids 欄位應為 None")
def assert_empty_tool_kb_ids_none(context) -> None:
    cfg: ToolRagConfig = context["tool_rag_config"]
    assert cfg.kb_ids is None
