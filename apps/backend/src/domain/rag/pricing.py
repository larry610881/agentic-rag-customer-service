"""LLM Token 定價計算"""

from src.domain.rag.value_objects import TokenUsage


def calculate_usage(
    model: str,
    input_tokens: int,
    output_tokens: int,
    pricing: dict[str, dict[str, float]],
    cache_read_tokens: int = 0,
    cache_creation_tokens: int = 0,
) -> TokenUsage:
    """根據模型定價計算 token 使用量與成本。

    input_tokens 應為「非快取 input」（各 LLMService 負責正規化）。

    pricing 格式：
        {"claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0}}
        可選 key: "cache_read", "cache_creation"（USD per 1M tokens）
        未設定時預設：cache_read = input × 0.10, cache_creation = input × 1.25
    """
    model_pricing = pricing.get(model, {})
    # Fallback: strip date suffix (e.g. "gpt-5.1-2025-11-13" → "gpt-5.1")
    if not model_pricing:
        for key in pricing:
            if model.startswith(key):
                model_pricing = pricing[key]
                break
    input_price = model_pricing.get("input", 0.0)
    output_price = model_pricing.get("output", 0.0)
    cache_read_price = model_pricing.get("cache_read", input_price * 0.10)
    cache_creation_price = model_pricing.get("cache_creation", input_price * 1.25)

    estimated_cost = (
        input_tokens * input_price / 1_000_000
        + cache_read_tokens * cache_read_price / 1_000_000
        + cache_creation_tokens * cache_creation_price / 1_000_000
        + output_tokens * output_price / 1_000_000
    )

    return TokenUsage(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost=estimated_cost,
        cache_read_tokens=cache_read_tokens,
        cache_creation_tokens=cache_creation_tokens,
    )
