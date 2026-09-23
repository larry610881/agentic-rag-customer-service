"""SQLAlchemyVersionMetricsRepository — 租戶＋版本範圍條件（Issue #101）。

四段查詢都以「該租戶該版本的 usage message_id」子查詢為界；
少了 tenant_id 就會把別租戶同版本 id 的訊息品質算進來。
"""

from __future__ import annotations

import asyncio
from collections import namedtuple
from typing import Any

import pytest

from src.infrastructure.db.repositories.version_metrics_repository import (
    SQLAlchemyVersionMetricsRepository,
)
from tests.unit.repositories.spy_session import FakeResult, SpySession


def _run(coro):
    return asyncio.run(coro)


class _Row(tuple):
    """SQLAlchemy Row 的 .tuple()。"""

    def tuple(self) -> tuple:  # noqa: A003
        return tuple(self)


class _Result(FakeResult):
    def one(self) -> Any:
        return self._rows[0]


class _Session(SpySession):
    """FakeResult 缺 one()：本檔自補。"""

    def queue_result(self, rows: list[Any] | None = None, rowcount: int = 0) -> None:
        self._queued.append(_Result(rows, rowcount))

    async def execute(self, stmt: Any, *args: Any, **kwargs: Any) -> FakeResult:
        self.statements.append(stmt)
        return self._queued.popleft() if self._queued else _Result([])


@pytest.fixture
def session() -> _Session:
    return _Session()


@pytest.fixture
def repo(session) -> SQLAlchemyVersionMetricsRepository:
    return SQLAlchemyVersionMetricsRepository(session)  # type: ignore[arg-type]


def test_every_query_scoped_to_tenant_and_version(session, repo):
    Eval = namedtuple("Eval", "layer score")
    session.queue_result([(3, 1200, 300, 0.0123456789)])
    session.queue_result([812.345])
    session.queue_result([Eval("L1", 0.81234), Eval("L2", None)])
    session.queue_result([_Row(("thumbs_up", 5)), _Row(("thumbs_down", 1))])

    m = _run(repo.get_metrics("tenant-a", "ver-1"))

    usage_sql, latency_sql, eval_sql, fb_sql = session.all_sql()
    for sql in (usage_sql, latency_sql, eval_sql, fb_sql):
        assert "token_usage_records.tenant_id = 'tenant-a'" in sql
        assert "token_usage_records.config_version_id = 'ver-1'" in sql
    assert "messages.id IN" in latency_sql
    assert "rag_evaluations.message_id IN" in eval_sql
    assert "feedback.message_id IN" in fb_sql

    assert m.version_id == "ver-1"
    assert m.message_count == 3
    assert (m.input_tokens, m.output_tokens) == (1200, 300)
    assert m.total_cost == 0.012346
    assert m.avg_latency_ms == 812.3
    assert m.eval_avg_by_layer == {"L1": 0.8123}
    assert (m.feedback_up, m.feedback_down) == (5, 1)


def test_empty_version_defaults(session, repo):
    session.queue_result([(None, None, None, None)])
    session.queue_result([None])
    m = _run(repo.get_metrics("tenant-a", "ver-x"))
    assert m.message_count == 0
    assert m.total_cost == 0.0
    assert m.avg_latency_ms is None
    assert m.eval_avg_by_layer == {}
    assert (m.feedback_up, m.feedback_down) == (0, 0)
