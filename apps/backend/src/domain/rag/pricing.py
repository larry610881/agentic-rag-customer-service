"""LLM Token 定價計算"""

from src.domain.rag.value_objects import TokenUsage


def calculate_usage(
    model: str,
    input_tokens: int,
    output_tokens: int,
    pricing: dict[str, dict[str, float]],
) -> TokenUsage:
    """根據模型定價計算 token 使用量與成本。

    pricing 格式：
        {"claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0}}
        價格單位：USD per 1M tokens
    """
    model_pricing = pricing.get(model, {})
    input_price = model_pricing.get("input", 0.0)
    output_price = model_pricing.get("output", 0.0)

    estimated_cost = (
        input_tokens * input_price / 1_000_000
        + output_tokens * output_price / 1_000_000
    )

    return TokenUsage(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        estimated_cost=estimated_cost,
    )
