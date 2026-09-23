"""CachedGuardRulesConfigRepository — 平台防護規則快取（含「不存在」）與寫入失效。"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.domain.security.guard_config import (
    GuardRulesConfig,
    GuardRulesConfigRepository,
)
from src.infrastructure.db.repositories.cached_guard_rules_config_repository import (
    CachedGuardRulesConfigRepository,
    invalidate_guard_rules_cache,
)


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _clear_cache():
    invalidate_guard_rules_cache()
    yield
    invalidate_guard_rules_cache()


def test_get_caches_config():
    cfg = GuardRulesConfig(input_rules=[{"pattern": "ignore previous"}])
    inner = AsyncMock(spec=GuardRulesConfigRepository)
    inner.get.return_value = cfg
    repo = CachedGuardRulesConfigRepository(inner)
    assert _run(repo.get()) is cfg
    assert _run(repo.get()) is cfg
    assert inner.get.await_count == 1


def test_missing_config_is_cached_as_none():
    inner = AsyncMock(spec=GuardRulesConfigRepository)
    inner.get.return_value = None
    repo = CachedGuardRulesConfigRepository(inner)
    assert _run(repo.get()) is None
    assert _run(repo.get()) is None
    assert inner.get.await_count == 1  # 未建設定時不每則訊息打 DB


def test_save_invalidates_so_new_rules_apply_immediately():
    old = GuardRulesConfig(input_rules=[])
    new = GuardRulesConfig(input_rules=[{"pattern": "x"}])
    inner = AsyncMock(spec=GuardRulesConfigRepository)
    inner.get.side_effect = [old, new]
    repo = CachedGuardRulesConfigRepository(inner)
    assert _run(repo.get()) is old
    _run(repo.save(new))
    inner.save.assert_awaited_once_with(new)
    assert _run(repo.get()) is new
