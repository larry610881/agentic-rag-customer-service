"""SQLAlchemyVisitorProfileRepository — 租戶過濾條件與實體映射（Issue #101）。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from src.domain.memory.entity import VisitorIdentity, VisitorProfile
from src.domain.memory.value_objects import VisitorIdentityId, VisitorProfileId
from src.infrastructure.db.models.visitor_identity_model import VisitorIdentityModel
from src.infrastructure.db.models.visitor_profile_model import VisitorProfileModel
from src.infrastructure.db.repositories.visitor_profile_repository import (
    SQLAlchemyVisitorProfileRepository,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


def _identity_model(**over) -> VisitorIdentityModel:
    data: dict = {
        "id": "vi-1",
        "profile_id": "vp-1",
        "tenant_id": "tenant-a",
        "source": "line",
        "external_id": "U123",
        "created_at": T0,
    }
    data.update(over)
    return VisitorIdentityModel(**data)


@pytest.fixture
def session() -> SpySession:
    return SpySession()


@pytest.fixture
def repo(session) -> SQLAlchemyVisitorProfileRepository:
    return SQLAlchemyVisitorProfileRepository(session)  # type: ignore[arg-type]


def test_find_identity_filters_tenant_source_external_id(session, repo):
    assert _run(repo.find_identity("tenant-a", "line", "U123")) is None
    sql = session.sql(0)
    assert "visitor_identities.tenant_id = 'tenant-a'" in sql
    assert "visitor_identities.source = 'line'" in sql
    assert "visitor_identities.external_id = 'U123'" in sql

    session.queue_result([_identity_model()])
    ident = _run(repo.find_identity("tenant-a", "line", "U123"))
    assert ident is not None
    assert (ident.id.value, ident.profile_id, ident.tenant_id) == (
        "vi-1", "vp-1", "tenant-a")
    assert (ident.source, ident.external_id) == ("line", "U123")


def test_find_by_id_loads_identities_of_profile(session, repo):
    assert _run(repo.find_by_id("vp-x")) is None
    session.get_result = VisitorProfileModel(
        id="vp-1", tenant_id="tenant-a", display_name="小明",
        created_at=T0, updated_at=T0,
    )
    session.queue_result([_identity_model()])
    profile = _run(repo.find_by_id("vp-1"))
    assert "visitor_identities.profile_id = 'vp-1'" in session.sql(-1)
    assert profile is not None
    assert profile.tenant_id == "tenant-a"
    assert profile.display_name == "小明"
    assert [i.external_id for i in profile.identities] == ["U123"]


def test_save_new_profile_adds_model(session, repo):
    p = VisitorProfile(id=VisitorProfileId(value="vp-9"), tenant_id="tenant-a",
                       display_name="n")
    _run(repo.save(p))
    (added,) = session.added
    assert isinstance(added, VisitorProfileModel)
    assert (added.id, added.tenant_id) == ("vp-9", "tenant-a")


def test_save_existing_profile_only_updates_display_name(session, repo):
    existing = VisitorProfileModel(id="vp-1", tenant_id="tenant-a",
                                   display_name="舊", created_at=T0, updated_at=T0)
    session.get_result = existing
    _run(repo.save(VisitorProfile(id=VisitorProfileId(value="vp-1"),
                                  tenant_id="tenant-b", display_name="新")))
    assert existing.display_name == "新"
    assert existing.tenant_id == "tenant-a"  # 不可藉 save 改租戶
    assert existing.updated_at > T0
    assert session.added == []


def test_save_identity_merges(session, repo):
    ident = VisitorIdentity(id=VisitorIdentityId(value="vi-9"), profile_id="vp-1",
                            tenant_id="tenant-a", source="widget", external_id="w1")
    _run(repo.save_identity(ident))
    (merged,) = session.merged
    assert isinstance(merged, VisitorIdentityModel)
    assert (merged.tenant_id, merged.source, merged.external_id) == (
        "tenant-a", "widget", "w1")
