"""共用 Usage 工具 — 從 LangChain messages 或 accumulated dict 提取 TokenUsage"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage

from src.domain.rag.value_objects import TokenUsage


def extract_usage_from_langchain_messages(
    messages: list[Any],
) -> TokenUsage | None:
    """遍歷 AIMessage，累加 usage_metadata（input_tokens/output_tokens）。

    LangChain ChatModel 在 AIMessage.usage_metadata 放置 token 統計，
    model_name 則在 response_metadata 中。
    """
    total_input = 0
    total_output = 0
    total_cache_read = 0
    total_cache_creation = 0
    model_name = "unknown"

    for msg in messages:
        if not isinstance(msg, AIMessage):
            continue
        meta = getattr(msg, "usage_metadata", None)
        if not meta:
            continue
        total_input += meta.get("input_tokens", 0)
        total_output += meta.get("output_tokens", 0)

        # Extract cache tokens from LangChain input_token_details
        details = meta.get("input_token_details") or {}
        if details:
            # Anthropic: cache_read / cache_creation (input_tokens 不含 cache)
            # OpenAI/DeepSeek: cached (input_tokens 已含 cached，需扣除)
            cache_read = details.get("cache_read", 0)
            cached = details.get("cached", 0)
            this_cache_read = cache_read or cached
            total_cache_read += this_cache_read
            total_cache_creation += details.get("cache_creation", 0)

            # 正規化：OpenAI 系的 input_tokens 包含 cached，需扣除避免重複計算
            if cached and not cache_read:
                total_input -= this_cache_read

        resp_meta = getattr(msg, "response_metadata", None) or {}
        if resp_meta.get("model_name"):
            model_name = resp_meta["model_name"]
        elif resp_meta.get("model"):
            model_name = resp_meta["model"]

    total = total_input + total_output + total_cache_read + total_cache_creation
    if total == 0:
        return None

    return TokenUsage(
        model=model_name,
        input_tokens=total_input,
        output_tokens=total_output,
        total_tokens=total,
        cache_read_tokens=total_cache_read,
        cache_creation_tokens=total_cache_creation,
    )


def extract_usage_from_accumulated(acc: dict[str, Any]) -> TokenUsage | None:
    """將 Router graph state 的 accumulated_usage dict 轉為 TokenUsage。"""
    if not acc:
        return None
    return TokenUsage(
        model=acc.get("model", "unknown"),
        input_tokens=acc.get("input_tokens", 0),
        output_tokens=acc.get("output_tokens", 0),
        total_tokens=acc.get("total_tokens", 0),
        estimated_cost=acc.get("estimated_cost", 0.0),
        cache_read_tokens=acc.get("cache_read_tokens", 0),
        cache_creation_tokens=acc.get("cache_creation_tokens", 0),
    )


def build_usage_event(usage: TokenUsage | None) -> dict[str, Any] | None:
    """產生標準 usage SSE 事件 dict。回傳 None 表示無資料。"""
    if usage is None or usage.total_tokens == 0:
        return None
    return {
        "type": "usage",
        "model": usage.model,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "total_tokens": usage.total_tokens,
        "estimated_cost": usage.estimated_cost,
        "cache_read_tokens": usage.cache_read_tokens,
        "cache_creation_tokens": usage.cache_creation_tokens,
    }
