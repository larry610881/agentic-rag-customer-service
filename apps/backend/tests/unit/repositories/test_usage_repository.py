"""SQLAlchemyUsageRepository — 用量查詢帶租戶條件、計費區間與分類過濾（Issue #101）。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from src.domain.usage.entity import UsageRecord
from src.infrastructure.db.models.usage_record_model import UsageRecordModel
from src.infrastructure.db.repositories.usage_repository import (
    SQLAlchemyUsageRepository,
    _cycle_range,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)
T1 = datetime(2026, 10, 1, tzinfo=timezone.utc)
TENANT_WHERE = "token_usage_records.tenant_id = 'tenant-a'"


def _run(coro):
    return asyncio.run(coro)


def _record_model(**over) -> UsageRecordModel:
    data: dict = {
        "id": "u-1",
        "tenant_id": "tenant-a",
        "request_type": "chat_web",
        "model": "gpt-x",
        "input_tokens": 100,
        "output_tokens": 50,
        "estimated_cost": 0.02,
        "cache_read_tokens": 10,
        "cache_creation_tokens": 5,
        "message_id": "m-1",
        "bot_id": "bot-1",
        "kb_id": None,
        "run_id": "run-1",
        "config_version_id": "v-1",
        "config_hash": "h",
        "points": 3,
        "reasoning_tokens": None,
        "estimated": None,
        "created_at": T0,
    }
    data.update(over)
    return UsageRecordModel(**data)


@pytest.fixture
def session() -> SpySession:
    return SpySession()


@pytest.fixture
def repo(session) -> SQLAlchemyUsageRepository:
    return SQLAlchemyUsageRepository(session)  # type: ignore[arg-type]


def test_table_name_matches_assertions():
    assert UsageRecordModel.__tablename__ == "token_usage_records"


def test_save_adds_all_billing_fields(session, repo):
    rec = UsageRecord(
        tenant_id="tenant-a",
        request_type="chat_web",
        model="gpt-x",
        input_tokens=10,
        output_tokens=5,
        estimated_cost=0.1,
        points=7,
        reasoning_tokens=2,
        estimated=True,
        run_id="r",
        config_version_id="v",
    )
    _run(repo.save(rec))
    (m,) = session.added
    assert m.tenant_id == "tenant-a"
    assert (m.points, m.reasoning_tokens, m.estimated) == (7, 2, True)
    assert (m.run_id, m.config_version_id) == ("r", "v")
    assert session.commits == 1


def test_find_by_tenant_filters_tenant_and_range_and_maps(session, repo):
    session.queue_result([_record_model()])
    recs = _run(repo.find_by_tenant("tenant-a", T0, T1))
    sql = session.sql()
    assert TENANT_WHERE in sql
    assert "token_usage_records.created_at >= '2026-09-01" in sql
    assert "token_usage_records.created_at <= '2026-10-01" in sql
    (r,) = recs
    assert r.total_tokens == 165  # 四個 raw 欄位加總
    assert (r.run_id, r.config_version_id) == ("run-1", "v-1")  # L3
    assert r.points == 3
    assert r.reasoning_tokens == 0 and r.estimated is False


def test_tenant_summary_aggregates_only_that_tenant(session, repo):
    session.queue_result(
        [
            _record_model(),
            _record_model(id="u-2", model="gpt-y", request_type="line", points=1),
        ]
    )
    s = _run(repo.get_tenant_summary("tenant-a"))
    assert TENANT_WHERE in session.sql()
    assert s.total_tokens == 330
    assert s.total_points == 4
    assert s.by_model == {"gpt-x": 165, "gpt-y": 165}
    assert s.by_request_type_points == {"chat_web": 3, "line": 1}


def test_model_cost_stats_filters_tenant(session, repo):
    session.queue_result(
        [
            SimpleNamespace(
                model="gpt-x",
                cnt=2,
                sum_input=None,
                sum_output=4,
                sum_cost=0.123456,
                avg_latency=None,
            )
        ]
    )
    (stat,) = _run(repo.get_model_cost_stats("tenant-a", T0, T1))
    sql = session.sql()
    assert TENANT_WHERE in sql
    assert "token_usage_records.created_at < '2026-10-01" in sql
    assert stat.input_tokens == 0
    assert stat.estimated_cost == 0.1235
    assert stat.avg_latency_ms == 0.0


def test_bot_usage_stats_filters_tenant(session, repo):
    session.queue_result(
        [
            SimpleNamespace(
                bot_id="bot-1",
                bot_name="客服",
                model="gpt-x",
                request_type="chat_web",
                cnt=3,
                sum_input=1,
                sum_output=2,
                sum_total=3,
                sum_cost=None,
                sum_points=None,
            )
        ]
    )
    (stat,) = _run(repo.get_bot_usage_stats("tenant-a", T0, T1))
    assert TENANT_WHERE in session.sql()
    assert stat.bot_name == "客服" and stat.points == 0 and stat.estimated_cost == 0


@pytest.mark.parametrize("by_category", [False, True])
def test_daily_and_monthly_stats_filter_tenant(session, repo, by_category):
    row = SimpleNamespace(
        dt="2026-09-01",
        month="2026-09",
        cnt=1,
        sum_input=1,
        sum_output=1,
        sum_total=2,
        sum_cost=0.5,
        sum_points=2,
        req_type="chat_web",
    )
    session.queue_result([row])
    (daily,) = _run(
        repo.get_daily_usage_stats("tenant-a", T0, T1, by_category=by_category)
    )
    assert TENANT_WHERE in session.sql()
    assert daily.request_type == ("chat_web" if by_category else None)

    session.queue_result([row])
    (monthly,) = _run(
        repo.get_monthly_usage_stats("tenant-a", T0, T1, by_category=by_category)
    )
    assert TENANT_WHERE in session.sql()
    assert monthly.month == "2026-09" and monthly.points == 2
    assert ("request_type" in session.sql().split("GROUP BY")[1]) is by_category


def test_sum_tokens_in_range_uses_half_open_range(session, repo):
    session.queue_result([1234])
    assert _run(repo.sum_tokens_in_range("tenant-a", T0, T1)) == 1234
    sql = session.sql()
    assert TENANT_WHERE in sql
    assert "created_at >= '2026-09-01" in sql and "created_at < '2026-10-01" in sql


def test_sum_points_in_cycle(session, repo):
    session.queue_result([None])
    assert _run(repo.sum_points_in_cycle("tenant-a", "2026-12")) == 0
    sql = session.sql()
    assert TENANT_WHERE in sql
    assert "'2026-12-01" in sql and "'2027-01-01" in sql


def test_billable_tokens_three_state_category_filter(session, repo):
    # [] → 全部不計入，不查 DB
    assert _run(repo.sum_billable_tokens_in_cycle("tenant-a", "2026-09", [])) == 0
    assert session.statements == []

    # None → 全部計入，無分類條件
    session.queue_result([10])
    assert _run(repo.sum_billable_tokens_in_cycle("tenant-a", "2026-12", None)) == 10
    assert TENANT_WHERE in session.sql()
    assert "request_type IN" not in session.sql()

    # 明確清單 → 自動 union 三個 eval 分類（L4：防自帶分類標頭逃 quota）
    session.queue_result([20])
    assert (
        _run(repo.sum_billable_tokens_in_cycle("tenant-a", "2026-09", ["chat_web"]))
        == 20
    )
    sql = session.sql()
    assert TENANT_WHERE in sql
    assert "request_type IN (" in sql
    for cat in ("chat_web", "eval_gate", "prompt_optimize", "playground"):
        assert f"'{cat}'" in sql


def test_cycle_range_year_rollover():
    assert _cycle_range("2026-12") == (
        datetime(2026, 12, 1, tzinfo=timezone.utc),
        datetime(2027, 1, 1, tzinfo=timezone.utc),
    )
    assert _cycle_range("2026-03")[1] == datetime(2026, 4, 1, tzinfo=timezone.utc)
