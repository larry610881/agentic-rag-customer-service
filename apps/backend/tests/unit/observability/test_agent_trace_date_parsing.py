"""Regression: agent_trace date_from/date_to 字串轉 datetime — S-KB-Followup.1

User report：observability/agent-traces 帶 date_from='2026-03-24T05:48:41Z'
回 500，asyncpg 抱怨 'operator does not exist: timestamp with time zone >= varchar'。
build_where 直接把 str 塞進 SQL 比較。

Fix：build_where 用 _parse_iso 把字串轉 tz-aware datetime。
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.application.observability.agent_trace_queries import (
    TraceFilters,
    _parse_iso,
    build_where,
)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("2026-03-24T05:48:41Z", datetime(2026, 3, 24, 5, 48, 41, tzinfo=timezone.utc)),
        ("2026-03-24T05:48:41+00:00", datetime(2026, 3, 24, 5, 48, 41, tzinfo=timezone.utc)),
        ("2026-03-24T05:48:41.932Z", datetime(2026, 3, 24, 5, 48, 41, 932000, tzinfo=timezone.utc)),
        ("2026-03-24T05:48:41", datetime(2026, 3, 24, 5, 48, 41, tzinfo=timezone.utc)),  # 沒 tz 預設 UTC
    ],
)
def test_parse_iso_handles_common_iso_formats(value, expected):
    assert _parse_iso(value) == expected


def test_build_where_accepts_iso_string_date_from():
    """date_from 為 ISO string，build_where 必須轉成 datetime 不能 raise。"""
    filters = TraceFilters(
        tenant_id="t-001",
        date_from="2026-03-24T05:48:41Z",
    )
    conds = build_where(filters)
    # 應該有 2 個條件：tenant_id + created_at >=
    assert len(conds) == 2


def test_build_where_accepts_iso_string_date_to():
    filters = TraceFilters(
        tenant_id="t-001",
        date_to="2026-04-23T23:59:59Z",
    )
    conds = build_where(filters)
    assert len(conds) == 2


def test_build_where_with_both_dates():
    filters = TraceFilters(
        tenant_id="t-001",
        date_from="2026-03-01T00:00:00Z",
        date_to="2026-04-23T23:59:59Z",
    )
    conds = build_where(filters)
    assert len(conds) == 3
