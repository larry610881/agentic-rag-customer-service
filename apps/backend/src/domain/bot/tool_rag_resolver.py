"""Per-tool RAG 參數繼承鏈解析（純 Domain 邏輯）。

繼承優先序：Worker per-tool → Bot per-tool → Bot 全域 default

任何層級的欄位為 ``None`` 代表「未覆蓋，沿用下一層」。
"""
from __future__ import annotations

from typing import Any

from src.domain.bot.entity import Bot
from src.domain.bot.worker_config import WorkerConfig

_FIELDS = (
    "rag_top_k",
    "rag_score_threshold",
    "rerank_enabled",
    "rerank_model",
    "rerank_top_n",
)


def resolve_tool_rag_params(
    *,
    tool_name: str,
    bot: Bot,
    worker: WorkerConfig | None = None,
) -> dict[str, Any]:
    """回傳該工具最終應使用的 RAG 參數。

    結果永遠包含 ``_FIELDS`` 全部 5 個 key，值從 Bot 全域預設為基底，
    依序被 Bot per-tool → Worker per-tool 的非 None 值覆蓋。
    """
    resolved: dict[str, Any] = {
        "rag_top_k": bot.llm_params.rag_top_k,
        "rag_score_threshold": bot.llm_params.rag_score_threshold,
        "rerank_enabled": bot.rerank_enabled,
        "rerank_model": bot.rerank_model,
        "rerank_top_n": bot.rerank_top_n,
    }

    overrides = []
    bot_tool = bot.tool_configs.get(tool_name)
    if bot_tool is not None:
        overrides.append(bot_tool)
    if worker is not None:
        worker_tool = worker.tool_configs.get(tool_name)
        if worker_tool is not None:
            overrides.append(worker_tool)

    for cfg in overrides:
        for key in _FIELDS:
            value = getattr(cfg, key)
            if value is not None:
                resolved[key] = value

    return resolved
