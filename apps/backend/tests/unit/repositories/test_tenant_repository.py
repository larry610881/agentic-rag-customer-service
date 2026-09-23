"""SQLAlchemyTenantRepository — 租戶主表的查詢、分頁與 merge 寫入（Issue #101）。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from src.domain.tenant.entity import Tenant
from src.domain.tenant.value_objects import TenantId
from src.infrastructure.db.models.tenant_model import TenantModel
from src.infrastructure.db.repositories.tenant_repository import (
    SQLAlchemyTenantRepository,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


def _model(**over) -> TenantModel:
    data: dict = {
        "id": "tenant-a",
        "name": "家樂福",
        "plan": "pro",
        "monthly_token_limit": 1000,
        "prompt_gate_enabled": True,
        "included_categories": ["chat_web"],
        "default_ocr_model": "ocr",
        "default_context_model": "ctx",
        "default_classification_model": "cls",
        "default_summary_model": "sum",
        "default_intent_model": "intent",
        "exhaustion_policy_override": "block",
        "block_message_override": "停用",
        "config_change_notify_fields": ["bot_prompt"],
        "created_at": T0,
        "updated_at": T0,
    }
    data.update(over)
    return TenantModel(**data)


@pytest.fixture
def session() -> SpySession:
    return SpySession()


@pytest.fixture
def repo(session) -> SQLAlchemyTenantRepository:
    return SQLAlchemyTenantRepository(session)  # type: ignore[arg-type]


def test_find_by_id_maps_all_settings(session, repo):
    session.queue_result([_model()])
    t = _run(repo.find_by_id("tenant-a"))
    assert "tenants.id = 'tenant-a'" in session.sql()
    assert t is not None
    assert (t.id.value, t.plan, t.monthly_token_limit) == ("tenant-a", "pro", 1000)
    assert t.included_categories == ["chat_web"]
    assert t.prompt_gate_enabled is True
    assert (t.exhaustion_policy_override, t.block_message_override) == (
        "block",
        "停用",
    )
    assert t.config_change_notify_fields == ["bot_prompt"]
    assert _run(repo.find_by_id("none")) is None


def test_find_by_name(session, repo):
    session.queue_result([_model()])
    assert _run(repo.find_by_name("家樂福")).id.value == "tenant-a"
    assert "tenants.name = '家樂福'" in session.sql()
    assert _run(repo.find_by_name("x")) is None


def test_find_all_paginates_and_count(session, repo):
    session.queue_result([_model(), _model(id="tenant-b")])
    ts = _run(repo.find_all(limit=2, offset=4))
    sql = session.sql()
    assert "LIMIT 2" in sql and "OFFSET 4" in sql
    assert [t.id.value for t in ts] == ["tenant-a", "tenant-b"]

    session.queue_result([2])
    assert _run(repo.count_all()) == 2


def test_save_merges_full_row(session, repo):
    t = Tenant(
        id=TenantId(value="tenant-a"),
        name="新名",
        plan="basic",
        included_categories=[],
        exhaustion_policy_override=None,
    )
    _run(repo.save(t))
    (m,) = session.merged
    assert (m.id, m.name, m.plan) == ("tenant-a", "新名", "basic")
    assert m.included_categories == []  # 空清單 = 全部不計入，不可變 None
    assert session.commits == 1
