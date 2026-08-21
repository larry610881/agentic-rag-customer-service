"""Regression: 驗證 history 落庫用新 session（H13）。"""

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

from src.application.eval_dataset.eval_use_cases import RunValidationEvalUseCase


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_persist_uses_factory_inside_independent_scope(monkeypatch):
    entered = {"n": 0}

    @asynccontextmanager
    async def _fake_scope():
        entered["n"] += 1
        yield

    import src.infrastructure.db.session_middleware as sm
    monkeypatch.setattr(sm, "independent_session_scope", _fake_scope)

    fresh_repo = AsyncMock()
    request_repo = AsyncMock()  # 不該被用（session 可能已死）
    uc = RunValidationEvalUseCase(
        eval_dataset_repository=AsyncMock(),
        optimization_run_repository=request_repo,
        run_repo_factory=lambda: fresh_repo,
    )
    _run(uc._persist_iteration({"id": "it-1"}))

    assert entered["n"] == 1, "history 未在 independent_session_scope 內落庫"
    fresh_repo.save_iteration.assert_awaited_once()
    request_repo.save_iteration.assert_not_called()


def test_persist_fallbacks_to_request_repo_without_factory():
    request_repo = AsyncMock()
    uc = RunValidationEvalUseCase(
        eval_dataset_repository=AsyncMock(),
        optimization_run_repository=request_repo,
    )
    _run(uc._persist_iteration({"id": "it-1"}))
    request_repo.save_iteration.assert_awaited_once()
