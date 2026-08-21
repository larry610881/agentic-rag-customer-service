"""Regression: arq job body 在 independent_session_scope 內執行（M30）。

worker 的 use case 透過 get_tracked_session()（ContextVar）建 session，但
SessionCleanupMiddleware 只在 HTTP scope 生效 → 背景 job 的 session 無人關閉：
以 SELECT 結尾的 job 留下 idle-in-transaction 連線、每分鐘 churn；長 LLM job 的
連線更會被 idle 逾時砍掉。execute_with_resilience 必須用 independent_session_scope
包住 coro_factory，確保 session 建立/關閉配對。
"""

import asyncio
from contextlib import asynccontextmanager

from src.worker_resilience import execute_with_resilience


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_coro_factory_runs_inside_session_scope(monkeypatch):
    events: list[str] = []

    @asynccontextmanager
    async def _fake_scope():
        events.append("enter")
        try:
            yield
        finally:
            events.append("exit")

    import src.infrastructure.db.session_middleware as sm
    monkeypatch.setattr(sm, "independent_session_scope", _fake_scope)

    async def _coro():
        events.append("job")
        return "ok"

    result = _run(
        execute_with_resilience(
            ctx={"job_try": 1},
            task_name="unit",
            task_id="t1",
            coro_factory=_coro,
        )
    )

    assert result == "ok"
    # job 在 scope 進入後、離開前執行 → session 被正確建立/關閉配對
    assert events == ["enter", "job", "exit"]
