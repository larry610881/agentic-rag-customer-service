"""Shared fixtures for pricing unit tests."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Iterable

import pytest

from src.domain.pricing.entity import ModelPricing, PricingRecalcAudit
from src.domain.pricing.repository import (
    ModelPricingRepository,
    PricingRecalcAuditRepository,
    UsageRecalcPort,
    UsageRecalcRow,
)


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class FakeModelPricingRepo(ModelPricingRepository):
    def __init__(self) -> None:
        self._items: list[ModelPricing] = []

    async def save(self, pricing: ModelPricing) -> None:
        self._items.append(pricing)

    async def find_by_id(self, pricing_id: str) -> ModelPricing | None:
        return next((p for p in self._items if p.id == pricing_id), None)

    async def find_active_version(
        self, provider: str, model_id: str, at: datetime
    ) -> ModelPricing | None:
        candidates = [
            p
            for p in self._items
            if p.provider == provider
            and p.model_id == model_id
            and p.effective_from <= at
            and (p.effective_to is None or p.effective_to > at)
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda p: p.effective_from)

    async def find_all_versions(
        self, provider: str | None = None, category: str | None = None
    ) -> list[ModelPricing]:
        result = list(self._items)
        if provider:
            result = [p for p in result if p.provider == provider]
        if category:
            result = [p for p in result if p.category.value == category]
        return result

    async def list_all_for_cache(self) -> list[ModelPricing]:
        return list(self._items)

    async def update_effective_to(
        self, pricing_id: str, effective_to: datetime
    ) -> None:
        for p in self._items:
            if p.id == pricing_id:
                p.effective_to = effective_to


class FakeAuditRepo(PricingRecalcAuditRepository):
    def __init__(self) -> None:
        self.saved: list[PricingRecalcAudit] = []

    async def save(self, audit: PricingRecalcAudit) -> None:
        self.saved.append(audit)

    async def list_recent(self, limit: int = 100) -> list[PricingRecalcAudit]:
        return list(
            sorted(self.saved, key=lambda a: a.executed_at, reverse=True)
        )[:limit]


class FakeUsageRecalcPort(UsageRecalcPort):
    def __init__(self, rows: Iterable[UsageRecalcRow] | None = None) -> None:
        self._rows: list[UsageRecalcRow] = list(rows or [])
        self.updates: list[tuple[str, float]] = []
        self.recalc_at: datetime | None = None

    def set_rows(self, rows: Iterable[UsageRecalcRow]) -> None:
        self._rows = list(rows)

    async def find_for_recalc(
        self,
        *,
        provider: str,
        model_id: str,
        recalc_from: datetime,
        recalc_to: datetime,
        limit: int,
    ) -> list[UsageRecalcRow]:
        # 假設呼叫者傳 model 對得上，就回全部
        return self._rows[: limit + 1]

    async def bulk_update_cost(
        self,
        *,
        updates: list[tuple[str, float]],
        recalc_at: datetime,
    ) -> None:
        self.updates = list(updates)
        self.recalc_at = recalc_at


class FakeCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[str, float | None]] = {}

    async def get(self, key: str) -> str | None:
        val = self._store.get(key)
        if val is None:
            return None
        return val[0]

    async def set(
        self, key: str, value: str, ttl_seconds: int | None = None
    ) -> None:
        self._store[key] = (value, ttl_seconds)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def force_expire(self, key: str) -> None:
        self._store.pop(key, None)


@pytest.fixture
def context():
    return {}
