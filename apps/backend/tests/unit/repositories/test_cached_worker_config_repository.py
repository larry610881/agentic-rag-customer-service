"""CachedWorkerConfigRepository — 以 bot_id 為鍵的 TTL 快取與寫入失效（Issue #101）。

快取鍵是 bot_id：不同 bot（不同租戶）的 worker 清單不可互相命中。
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.domain.bot.worker_config import WorkerConfig
from src.domain.bot.worker_repository import WorkerConfigRepository
from src.infrastructure.db.repositories import cached_worker_config_repository as mod
from src.infrastructure.db.repositories.cached_worker_config_repository import (
    CachedWorkerConfigRepository,
    invalidate_worker_config_cache,
)


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _clear_cache():
    invalidate_worker_config_cache()
    yield
    invalidate_worker_config_cache()


@pytest.fixture
def inner() -> AsyncMock:
    inner = AsyncMock(spec=WorkerConfigRepository)

    async def by_bot(bot_id):
        return [WorkerConfig(id=f"w-{bot_id}", bot_id=bot_id)]

    inner.find_by_bot_id.side_effect = by_bot
    return inner


def test_find_by_bot_id_cached_per_bot(inner):
    repo = CachedWorkerConfigRepository(inner)
    a1 = _run(repo.find_by_bot_id("bot-a"))
    a2 = _run(repo.find_by_bot_id("bot-a"))
    b = _run(repo.find_by_bot_id("bot-b"))

    assert inner.find_by_bot_id.await_count == 2  # bot-a 第二次命中快取
    assert [w.bot_id for w in a2] == ["bot-a"]
    assert [w.bot_id for w in b] == ["bot-b"]  # 不同 bot 不共用
    # 回傳副本：呼叫端改清單不污染快取
    a1.clear()
    assert len(_run(repo.find_by_bot_id("bot-a"))) == 1


def test_save_and_delete_invalidate(inner):
    repo = CachedWorkerConfigRepository(inner)
    _run(repo.find_by_bot_id("bot-a"))
    _run(repo.save(WorkerConfig(id="w", bot_id="bot-a")))
    inner.save.assert_awaited_once()
    assert len(mod._CACHE) == 0

    _run(repo.find_by_bot_id("bot-a"))
    _run(repo.delete("w"))
    inner.delete.assert_awaited_once_with("w")
    assert len(mod._CACHE) == 0
    _run(repo.find_by_bot_id("bot-a"))
    assert inner.find_by_bot_id.await_count == 3


def test_find_by_id_not_cached(inner):
    inner.find_by_id.return_value = None
    repo = CachedWorkerConfigRepository(inner)
    assert _run(repo.find_by_id("w")) is None
    assert _run(repo.find_by_id("w")) is None
    assert inner.find_by_id.await_count == 2
