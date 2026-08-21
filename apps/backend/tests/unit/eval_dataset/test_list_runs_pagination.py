"""Regression: ListRunsUseCase 分頁合併正確（M27）。"""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from src.application.eval_dataset.run_use_cases import ListRunsUseCase


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _active(run_id):
    return SimpleNamespace(
        run_id=run_id, tenant_id="t1", dataset_id="d", dataset_name="n",
        target_field="base_prompt", bot_id="b", status="running",
        baseline_score=0.0, best_score=0.0, current_iteration=1,
        max_iterations=20, total_api_calls=0, stopped_reason="",
        started_at=datetime.now(timezone.utc), completed_at=None,
    )


def _db(run_id):
    return {
        "run_id": run_id, "tenant_id": "t1", "target_field": "base_prompt",
        "bot_id": "b", "run_type": "optimization", "baseline_score": 0.0,
        "best_score": 0.0, "total_iterations": 3,
        "started_at": datetime.now(timezone.utc),
    }


def _make_uc(active_ids, db_ids):
    run_manager = MagicMock()
    run_manager.list_runs = MagicMock(return_value=[_active(i) for i in active_ids])
    repo = AsyncMock()

    async def _list(tenant_id, *, limit, offset):
        return [_db(i) for i in db_ids][offset:offset + limit]

    repo.list_runs = AsyncMock(side_effect=_list)
    return ListRunsUseCase(repo, run_manager)


def test_active_only_on_first_page_and_no_db_run_lost():
    # 1 active + 4 db（DB#0..3），page_size=2
    uc = _make_uc(active_ids=["A"], db_ids=["D0", "D1", "D2", "D3"])

    page1 = _run(uc.execute("t1", limit=2, offset=0))
    ids1 = [r["run_id"] for r in page1]
    assert ids1 == ["A", "D0"]  # active 在頂，DB#0 不被截掉

    page2 = _run(uc.execute("t1", limit=2, offset=2))
    ids2 = [r["run_id"] for r in page2]
    # 承接 page1 之後：DB#1, DB#2（active 不再重複出現）
    assert "A" not in ids2
    assert ids2 == ["D1", "D2"]

    page3 = _run(uc.execute("t1", limit=2, offset=4))
    ids3 = [r["run_id"] for r in page3]
    assert ids3 == ["D3"]  # 最後一筆，不遺失


def test_no_active_runs():
    uc = _make_uc(active_ids=[], db_ids=["D0", "D1"])
    page1 = _run(uc.execute("t1", limit=2, offset=0))
    assert [r["run_id"] for r in page1] == ["D0", "D1"]
