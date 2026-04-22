"""InMemoryPricingCache — S-Pricing.1

啟動時從 DB load 全部 pricing 版本，以 (provider, model_id) → list[ModelPricing]
索引，lookup 時按 effective_from 排序回答「某時點的有效價格」。

Hot-path 用：RecordUsageUseCase._estimate_cost_from_registry 先打這個 cache。
Cache miss 時由 record_usage 自行 fallback 到 DEFAULT_MODELS。
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime
from typing import Callable

import structlog

from src.domain.pricing.entity import ModelPricing
from src.domain.pricing.repository import ModelPricingRepository

logger = structlog.get_logger(__name__)


class InMemoryPricingCache:
    """Thread-safe-ish 記憶體快取。單 pod 用，足夠 POC。

    未來 multi-pod 需接 Redis pub/sub 做 invalidation（不在本 sprint 範圍）。
    """

    def __init__(
        self, repo_factory: Callable[[], ModelPricingRepository]
    ) -> None:
        """repo_factory 每次回傳新 Repo + 新 session（避免 long-lived session）。"""
        self._repo_factory = repo_factory
        # (provider, model_id) -> list[ModelPricing]（effective_from 升序）
        self._index: dict[tuple[str, str], list[ModelPricing]] = defaultdict(
            list
        )
        self._lock = asyncio.Lock()

    async def refresh(self) -> None:
        """從 DB load 所有版本（含未生效 + 已停用）；啟動 + 變更後呼叫。"""
        async with self._lock:
            try:
                repo = self._repo_factory()
                all_versions = await repo.list_all_for_cache()
            except Exception:
                logger.warning("pricing.cache.refresh_failed", exc_info=True)
                return

            new_index: dict[tuple[str, str], list[ModelPricing]] = defaultdict(
                list
            )
            for p in all_versions:
                new_index[(p.provider, p.model_id)].append(p)
            for key in new_index:
                new_index[key].sort(key=lambda x: x.effective_from)
            self._index = new_index
            logger.info(
                "pricing.cache.refreshed",
                entries=len(all_versions),
                unique_models=len(new_index),
            )

    def lookup(
        self, model_spec: str, at: datetime
    ) -> dict[str, float] | None:
        """回傳 calculate_usage 吃的 pricing dict，或 None（cache miss）。

        model_spec 可為 "provider:model_id" 或裸 "model_id"。後者會嘗試所有
        provider 找第一個匹配（RecordUsageUseCase 目前已有 `lookup_model` 剝
        前綴邏輯，此方法兼容兩種 shape）。
        """
        provider, model_id = _parse_model_spec(model_spec)
        if provider is not None:
            versions = self._index.get((provider, model_id), [])
            return _pick_at(versions, at)

        # 無 provider 前綴 → 掃所有 (*, model_id)
        for (_, mid), versions in self._index.items():
            if mid == model_id:
                result = _pick_at(versions, at)
                if result is not None:
                    return result
        return None


def _parse_model_spec(model_spec: str) -> tuple[str | None, str]:
    if ":" in model_spec:
        provider, model_id = model_spec.split(":", 1)
        return provider, model_id
    return None, model_spec


def _pick_at(
    versions: list[ModelPricing], at: datetime
) -> dict[str, float] | None:
    """從已排序的 version list 中找 at 時點的生效版本。"""
    chosen: ModelPricing | None = None
    for v in versions:
        if v.effective_from > at:
            break
        if v.effective_to is not None and v.effective_to <= at:
            continue
        chosen = v
    return chosen.rate.as_calculate_usage_dict() if chosen else None
