"""Pricing Value Objects"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PricingCategory(StrEnum):
    LLM = "llm"
    EMBEDDING = "embedding"


@dataclass(frozen=True)
class PriceRate:
    """LLM 模型四段價格（USD per 1,000,000 tokens）。

    對齊 domain.rag.pricing.calculate_usage 吃的 dict shape：
        {"input": ..., "output": ..., "cache_read": ..., "cache_creation": ...}
    """

    input_price: float
    output_price: float
    cache_read_price: float = 0.0
    cache_creation_price: float = 0.0

    def __post_init__(self) -> None:
        for name, value in (
            ("input_price", self.input_price),
            ("output_price", self.output_price),
            ("cache_read_price", self.cache_read_price),
            ("cache_creation_price", self.cache_creation_price),
        ):
            if value < 0:
                raise ValueError(f"{name} must be non-negative, got {value!r}")

    def as_calculate_usage_dict(self) -> dict[str, float]:
        """轉成 calculate_usage(pricing=...) 吃的格式"""
        d: dict[str, float] = {
            "input": self.input_price,
            "output": self.output_price,
        }
        if self.cache_read_price > 0:
            d["cache_read"] = self.cache_read_price
        if self.cache_creation_price > 0:
            d["cache_creation"] = self.cache_creation_price
        return d
