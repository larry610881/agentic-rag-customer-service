"""Regression: log cleanup 單次迭代在 independent_session_scope 內執行（H14）。"""

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import src.main as main_mod


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_cleanup_runs_inside_independent_session_scope(monkeypatch):
    entered = {"count": 0, "exited": 0}

    @asynccontextmanager
    async def _fake_scope():
        entered["count"] += 1
        try:
            yield
        finally:
            entered["exited"] += 1

    # patch 掉真正的 session middleware（helper 內部 import）
    import src.infrastructure.db.session_middleware as sm
    monkeypatch.setattr(sm, "independent_session_scope", _fake_scope)

    repo = AsyncMock()
    repo.get = AsyncMock(return_value=None)  # policy None → 直接 return
    container = MagicMock()
    container.log_retention_policy_repository = MagicMock(return_value=repo)

    _run(main_mod._run_log_cleanup_once(container))

    assert entered["count"] == 1, "清理未在 independent_session_scope 內執行"
    assert entered["exited"] == 1, "session scope 未正確關閉"
