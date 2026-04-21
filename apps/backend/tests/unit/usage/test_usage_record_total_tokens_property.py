"""UsageRecord.total_tokens — Token-Gov.6 Property 不變性

冗餘 DB 欄位刪除後，`total_tokens` 改為 @property：
= input_tokens + output_tokens + cache_read_tokens + cache_creation_tokens

紅燈期：當前 total_tokens 仍是 field，default 0，傳 0 時即使 input/output/cache 有值
也會回 0（與 property 行為不一致 → 測試 FAIL）。

實作 Stage 4.1 後變綠。

Plan: .claude/plans/b-bug-delightful-starlight.md
Issue: #36
"""
from __future__ import annotations

from src.domain.usage.entity import UsageRecord


def test_total_tokens_sums_input_output_cache_when_all_set():
    """完整案例：4 個 raw 欄位都有值 → total = 總和"""
    record = UsageRecord(
        input_tokens=100,
        output_tokens=50,
        cache_read_tokens=30,
        cache_creation_tokens=20,
    )
    assert record.total_tokens == 200


def test_total_tokens_equals_zero_when_all_raw_fields_zero():
    """邊界案例：沒用量 → total = 0"""
    record = UsageRecord()
    assert record.total_tokens == 0


def test_total_tokens_includes_cache_read_only():
    """cache_read 單獨有值（例如純 cache hit）"""
    record = UsageRecord(
        input_tokens=0, output_tokens=0,
        cache_read_tokens=60_416, cache_creation_tokens=0,
    )
    assert record.total_tokens == 60_416


def test_total_tokens_includes_cache_creation_only():
    """cache_creation 單獨有值（首次寫入快取）"""
    record = UsageRecord(
        input_tokens=0, output_tokens=0,
        cache_read_tokens=0, cache_creation_tokens=5_000,
    )
    assert record.total_tokens == 5_000


def test_total_tokens_equals_components_sum_carrefour_2026_04():
    """驗證 Carrefour 2026-04 全月加總（實際生產資料）"""
    record = UsageRecord(
        input_tokens=218_556,
        output_tokens=17_020,
        cache_read_tokens=60_416,
        cache_creation_tokens=0,
    )
    assert record.total_tokens == 295_992


def test_total_tokens_not_in_constructor_signature():
    """Token-Gov.6 Stage 4.1 後 UsageRecord 不再接受 total_tokens 參數。

    紅燈期：目前能 UsageRecord(total_tokens=999)，此 test 失敗。
    Stage 4.1 改 property 後：不可傳 total_tokens（dataclass 不再有該 field）。
    """
    import inspect
    params = inspect.signature(UsageRecord).parameters
    assert "total_tokens" not in params, (
        "UsageRecord 建構子不應再有 total_tokens 參數（Token-Gov.6：冗餘已刪除）"
    )


def test_total_tokens_is_read_only_property():
    """驗證為 property 而非 field（無法 assign）"""
    record = UsageRecord(input_tokens=10, output_tokens=20)
    try:
        record.total_tokens = 999  # type: ignore[misc]
        # 若走到這行代表 field（可 assign），應失敗
        raise AssertionError("total_tokens 應為 read-only property，不可 assign")
    except AttributeError:
        pass  # 期望行為
