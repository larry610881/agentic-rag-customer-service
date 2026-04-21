"""UsageRepository.sum_tokens_in_range — Token-Gov.6 共用 SUM 入口

驗證 Repository Interface：
- abstract sum_tokens_in_range 方法存在
- sum_tokens_in_cycle 保留為 delegator（透過 range 算出 cycle 對應區間）

Infrastructure 層的真實 SQL 行為由 integration test 覆蓋；本檔只驗 interface。

Plan: .claude/plans/b-bug-delightful-starlight.md
Issue: #36
"""
from __future__ import annotations

import asyncio
import inspect
from datetime import datetime, timezone

from src.domain.usage.repository import UsageRepository


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_sum_tokens_in_range_is_abstract():
    """新 abstract method 出現在 UsageRepository interface。"""
    assert hasattr(UsageRepository, "sum_tokens_in_range"), (
        "UsageRepository 應宣告 sum_tokens_in_range abstract method"
    )
    sig = inspect.signature(UsageRepository.sum_tokens_in_range)
    params = sig.parameters
    assert "tenant_id" in params
    assert "start" in params
    assert "end" in params


def test_sum_tokens_in_cycle_delegates_to_sum_tokens_in_range():
    """sum_tokens_in_cycle 改為薄 wrapper，內部 delegate 到 sum_tokens_in_range。"""

    captured: list[tuple[str, datetime, datetime]] = []

    class FakeRepo(UsageRepository):
        # abstract method 新實作
        async def sum_tokens_in_range(
            self, tenant_id: str, start: datetime, end: datetime
        ) -> int:
            captured.append((tenant_id, start, end))
            return 42

        # 其他 abstracts — 最小 stub（本 test 不觸發）
        async def save(self, record): ...  # type: ignore[override]
        async def find_by_tenant(self, tenant_id, start_date=None, end_date=None):  # type: ignore[override]
            return []
        async def get_tenant_summary(self, tenant_id, start_date=None, end_date=None):  # type: ignore[override]
            raise NotImplementedError
        async def get_model_cost_stats(self, tenant_id, start_date=None, end_date=None):  # type: ignore[override]
            return []
        async def get_bot_usage_stats(self, tenant_id, start_date=None, end_date=None):  # type: ignore[override]
            return []
        async def get_daily_usage_stats(  # type: ignore[override]
            self, tenant_id, start_date=None, end_date=None
        ):
            return []

        async def get_monthly_usage_stats(  # type: ignore[override]
            self, tenant_id, start_date=None, end_date=None
        ):
            return []

    repo = FakeRepo()
    result = _run(repo.sum_tokens_in_cycle("t-1", "2026-04"))

    assert result == 42
    assert len(captured) == 1
    tenant_id, start, end = captured[0]
    assert tenant_id == "t-1"
    # 2026-04 區間應為 [2026-04-01 00:00 UTC, 2026-05-01 00:00 UTC)
    assert start == datetime(2026, 4, 1, tzinfo=timezone.utc)
    assert end == datetime(2026, 5, 1, tzinfo=timezone.utc)


def test_sum_tokens_in_cycle_year_boundary():
    """12 月的下一個月應跨年到 1 月。"""

    captured: list[tuple[datetime, datetime]] = []

    class FakeRepo(UsageRepository):
        async def sum_tokens_in_range(self, tenant_id, start, end):  # type: ignore[override]
            captured.append((start, end))
            return 0

        async def save(self, record): ...  # type: ignore[override]
        async def find_by_tenant(self, tenant_id, start_date=None, end_date=None):  # type: ignore[override]
            return []
        async def get_tenant_summary(self, tenant_id, start_date=None, end_date=None):  # type: ignore[override]
            raise NotImplementedError
        async def get_model_cost_stats(self, tenant_id, start_date=None, end_date=None):  # type: ignore[override]
            return []
        async def get_bot_usage_stats(self, tenant_id, start_date=None, end_date=None):  # type: ignore[override]
            return []
        async def get_daily_usage_stats(  # type: ignore[override]
            self, tenant_id, start_date=None, end_date=None
        ):
            return []

        async def get_monthly_usage_stats(  # type: ignore[override]
            self, tenant_id, start_date=None, end_date=None
        ):
            return []

    repo = FakeRepo()
    _run(repo.sum_tokens_in_cycle("t-1", "2026-12"))

    assert len(captured) == 1
    start, end = captured[0]
    assert start == datetime(2026, 12, 1, tzinfo=timezone.utc)
    assert end == datetime(2027, 1, 1, tzinfo=timezone.utc)
