"""Pricing Repository Interfaces"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from src.domain.pricing.entity import ModelPricing, PricingRecalcAudit


@dataclass(frozen=True)
class UsageRecalcRow:
    """回溯重算範圍內的 usage row 輕量 DTO（不洩漏 UsageRecord 全貌到 Pricing）"""

    id: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    estimated_cost: float


class ModelPricingRepository(ABC):
    @abstractmethod
    async def save(self, pricing: ModelPricing) -> None: ...

    @abstractmethod
    async def find_by_id(self, pricing_id: str) -> ModelPricing | None: ...

    @abstractmethod
    async def find_active_version(
        self, provider: str, model_id: str, at: datetime
    ) -> ModelPricing | None:
        """回傳在 `at` 時點生效的唯一版本（effective_from <= at < effective_to）。"""

    @abstractmethod
    async def find_all_versions(
        self,
        provider: str | None = None,
        category: str | None = None,
    ) -> list[ModelPricing]:
        """列出所有版本（含已排程未生效、已停用）。"""

    @abstractmethod
    async def list_all_for_cache(self) -> list[ModelPricing]:
        """PricingCache load / refresh：回傳所有版本（含排程未生效 + 已停用）。

        Cache 需要完整索引才能回答「任意時點的價格」，包含未來生效版本。
        """

    @abstractmethod
    async def update_effective_to(
        self, pricing_id: str, effective_to: datetime
    ) -> None: ...


class PricingRecalcAuditRepository(ABC):
    @abstractmethod
    async def save(self, audit: PricingRecalcAudit) -> None: ...

    @abstractmethod
    async def list_recent(self, limit: int = 100) -> list[PricingRecalcAudit]: ...


class UsageRecalcPort(ABC):
    """Pricing domain 專用的 usage 查詢 / 更新 port。

    不依賴 UsageRecord 物件，避免 Pricing 跨 context 引用 Usage Entity。
    實作在 infrastructure/pricing/usage_recalc_adapter.py。
    """

    @abstractmethod
    async def find_for_recalc(
        self,
        *,
        provider: str,
        model_id: str,
        recalc_from: datetime,
        recalc_to: datetime,
        limit: int,
    ) -> list[UsageRecalcRow]:
        """查區間內符合 (provider, model_id) 的 token_usage_records。

        `model` 欄位可能是 "provider:model_id" 或裸 "model_id"（S-LLM-Cache.1
        pricing lookup normalize 過）→ 實作需 WHERE model IN
        (provider:model_id, model_id)。limit 是保險上限；實作回傳超過 limit
        時應拋例外（避免一次性撈百萬 row）。
        """

    @abstractmethod
    async def bulk_update_cost(
        self,
        *,
        updates: list[tuple[str, float]],
        recalc_at: datetime,
    ) -> None:
        """交易內一次更新多筆：(row_id, new_estimated_cost) + 設 cost_recalc_at。"""
