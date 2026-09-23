"""SQLAlchemyAbuseSettingsRepository — 分層設定 scope 條件（Issue #101）。

tenant 層的覆寫以 (scope_kind='tenant', scope_id=<tenant_id>) 定位；
get / save 的 WHERE 必須同時鎖住兩個欄位，否則會讀寫到別的租戶那層。
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from src.domain.abuse.settings import AbuseSettings
from src.infrastructure.db.models.abuse_settings_model import AbuseSettingsModel
from src.infrastructure.db.repositories.abuse_settings_repository import (
    SQLAlchemyAbuseSettingsRepository,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


def _model(**over) -> AbuseSettingsModel:
    data: dict = {
        "id": "as-1",
        "scope_kind": "tenant",
        "scope_id": "tenant-a",
        "overrides": {"mode": "monitor"},
        "updated_by": "admin",
        "updated_at": T0,
    }
    data.update(over)
    return AbuseSettingsModel(**data)


@pytest.fixture
def session() -> SpySession:
    return SpySession()


@pytest.fixture
def repo(session) -> SQLAlchemyAbuseSettingsRepository:
    return SQLAlchemyAbuseSettingsRepository(session)  # type: ignore[arg-type]


def test_get_filters_scope_kind_and_scope_id(session, repo):
    assert _run(repo.get("tenant", "tenant-a")) is None
    sql = session.sql(0)
    assert "abuse_settings.scope_kind = 'tenant'" in sql
    assert "abuse_settings.scope_id = 'tenant-a'" in sql

    session.queue_result([_model()])
    s = _run(repo.get("tenant", "tenant-a"))
    assert isinstance(s, AbuseSettings)
    assert (s.scope_kind, s.scope_id) == ("tenant", "tenant-a")
    assert s.overrides == {"mode": "monitor"}
    assert s.updated_by == "admin"


def test_save_new_row(session, repo):
    settings = AbuseSettings(scope_kind="tenant", scope_id="tenant-b",
                             overrides={"mode": "enforce"}, updated_by="u")
    _run(repo.save(settings))
    sql = session.sql(0)
    assert "abuse_settings.scope_kind = 'tenant'" in sql
    assert "abuse_settings.scope_id = 'tenant-b'" in sql
    (added,) = session.added
    assert isinstance(added, AbuseSettingsModel)
    assert (added.scope_kind, added.scope_id) == ("tenant", "tenant-b")
    assert added.overrides == {"mode": "enforce"}
    assert session.commits == 1


def test_save_existing_row_updates_overrides(session, repo):
    existing = _model()
    session.queue_result([existing])
    _run(repo.save(AbuseSettings(scope_kind="tenant", scope_id="tenant-a",
                                 overrides={"mode": "off"}, updated_by="u2")))
    assert session.added == []
    assert existing.overrides == {"mode": "off"}
    assert existing.updated_by == "u2"


def test_list_profiles_only_profile_scope(session, repo):
    session.queue_result([_model(scope_kind="profile", scope_id="strict")])
    (p,) = _run(repo.list_profiles())
    sql = session.sql(0)
    assert "abuse_settings.scope_kind = 'profile'" in sql
    assert "ORDER BY abuse_settings.scope_id" in sql
    assert p.scope_id == "strict"
