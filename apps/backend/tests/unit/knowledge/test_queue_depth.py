"""Regression: queue_depth 必須濾掉 cron，否則 reaper 的「見底」判準永遠不成立。

2026-09-08 首次上線時用的是 ZCARD，而 arq 把 cron 也放進同一個 sorted set，
本專案有兩支每分鐘的 cron，於是 queue_depth 恆 >= 1，safety net 形同虛設
（實測 log：queue_depth=2 scanned=3 failed=0 skipped=3）。
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from src.infrastructure.queue import arq_pool


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _pool_with(members):
    pool = AsyncMock()
    pool.default_queue_name = "arq:queue"
    pool.zrange.return_value = members
    return pool


def test_只剩下_cron_時視為佇列見底():
    pool = _pool_with(
        [b"cron:drain_outbox_task:1757", b"cron:conversation_summary_scan_task:1757"]
    )
    with patch.object(arq_pool, "get_arq_pool", AsyncMock(return_value=pool)):
        assert run(arq_pool.queue_depth("redis://x")) == 0


def test_業務工作要被算進去():
    pool = _pool_with([b"cron:drain_outbox_task:1757", b"abc123", b"def456"])
    with patch.object(arq_pool, "get_arq_pool", AsyncMock(return_value=pool)):
        assert run(arq_pool.queue_depth("redis://x")) == 2


def test_探測失敗回負一讓呼叫端走保守路徑():
    with patch.object(arq_pool, "get_arq_pool", AsyncMock(side_effect=OSError("boom"))):
        assert run(arq_pool.queue_depth("redis://x")) == -1
