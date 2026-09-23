"""SQLAlchemyRateLimitConfigRepository — 租戶 / 全域預設的查詢條件（Issue #101）。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from src.domain.ratelimit.entity import RateLimitConfig
from src.domain.ratelimit.value_objects import EndpointGroup, RateLimitConfigId
from src.infrastructure.db.models.rate_limit_config_model import (
    RateLimitConfigModel,
)
from src.infrastructure.db.repositories.rate_limit_config_repository import (
    SQLAlchemyRateLimitConfigRepository,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


def _model(**over) -> RateLimitConfigModel:
    data: dict = {
        "id": "rl-1",
        "tenant_id": "tenant-a",
        "endpoint_group": "rag",
        "requests_per_minute": 60,
        "burst_size": 80,
        "per_user_requests_per_minute": 10,
        "created_at": T0,
        "updated_at": T0,
    }
    data.update(over)
    return RateLimitConfigModel(**data)


@pytest.fixture
def session() -> SpySession:
    return SpySession()


@pytest.fixture
def repo(session) -> SQLAlchemyRateLimitConfigRepository:
    return SQLAlchemyRateLimitConfigRepository(session)  # type: ignore[arg-type]


def test_find_by_tenant_and_group_scopes_tenant(session, repo):
    session.queue_result([_model()])
    cfg = _run(repo.find_by_tenant_and_group("tenant-a", "rag"))
    sql = session.sql()
    assert "rate_limit_configs.tenant_id = 'tenant-a'" in sql
    assert "rate_limit_configs.endpoint_group = 'rag'" in sql
    assert cfg is not None
    assert cfg.endpoint_group is EndpointGroup.RAG
    assert cfg.per_user_requests_per_minute == 10


def test_find_by_tenant_and_group_none_means_global_default(session, repo):
    assert _run(repo.find_by_tenant_and_group(None, "auth")) is None
    sql = session.sql()
    assert "rate_limit_configs.tenant_id IS NULL" in sql
    assert "rate_limit_configs.endpoint_group = 'auth'" in sql


def test_find_defaults_and_all_by_tenant(session, repo):
    session.queue_result([_model(tenant_id=None)])
    (d,) = _run(repo.find_defaults())
    assert d.tenant_id is None
    assert "rate_limit_configs.tenant_id IS NULL" in session.sql()

    _run(repo.find_all_by_tenant("tenant-b"))
    assert "rate_limit_configs.tenant_id = 'tenant-b'" in session.sql()


def test_save_new_and_update(session, repo):
    cfg = RateLimitConfig(
        id=RateLimitConfigId(value="rl-9"),
        tenant_id="tenant-a",
        endpoint_group=EndpointGroup.FEEDBACK,
        requests_per_minute=5,
    )
    _run(repo.save(cfg))
    (m,) = session.added
    assert (m.tenant_id, m.endpoint_group, m.requests_per_minute) == (
        "tenant-a",
        "feedback",
        5,
    )

    existing = _model()
    session.get_result = existing
    cfg.id = RateLimitConfigId(value="rl-1")
    _run(repo.save(cfg))
    assert (existing.endpoint_group, existing.requests_per_minute) == ("feedback", 5)
    assert existing.updated_at > T0


def test_delete_by_id(session, repo):
    _run(repo.delete("rl-1"))
    assert "DELETE FROM rate_limit_configs" in session.sql()
    assert "rate_limit_configs.id = 'rl-1'" in session.sql()
