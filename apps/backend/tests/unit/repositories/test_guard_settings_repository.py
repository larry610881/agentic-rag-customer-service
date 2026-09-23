"""SQLAlchemyGuardSettingsRepository（含共用的分層設定實作）— scope 定位與 upsert。

guard_settings 以 (scope_kind, scope_id) 定位；tenant 層的 scope_id 就是 tenant_id，
所以「查租戶層卻沒帶 scope_id」等於讀到別家的防護設定。這裡釘住兩個條件都在。
（_layered_settings_repository 由本檔與 test_abuse_settings_repository 共同覆蓋。）
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from src.domain.security.guard_stages import GuardSettings
from src.domain.settings.layered import SCOPE_PROFILE, SCOPE_TENANT
from src.infrastructure.db.models.guard_settings_model import GuardSettingsModel
from src.infrastructure.db.repositories.guard_settings_repository import (
    SQLAlchemyGuardSettingsRepository,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


def _model(**over) -> GuardSettingsModel:
    data: dict = {
        "id": "gs-1",
        "scope_kind": "tenant",
        "scope_id": "tenant-a",
        "overrides": {"input_guard": "enforce"},
        "updated_by": "admin",
        "updated_at": T0,
    }
    data.update(over)
    return GuardSettingsModel(**data)


@pytest.fixture
def session() -> SpySession:
    return SpySession()


@pytest.fixture
def repo(session) -> SQLAlchemyGuardSettingsRepository:
    return SQLAlchemyGuardSettingsRepository(session)  # type: ignore[arg-type]


def test_get_requires_scope_kind_and_id(session, repo):
    session.queue_result([_model()])
    s = _run(repo.get(SCOPE_TENANT, "tenant-a"))
    sql = session.sql()
    assert "guard_settings.scope_kind = 'tenant'" in sql
    assert "guard_settings.scope_id = 'tenant-a'" in sql
    assert isinstance(s, GuardSettings)
    assert s.overrides == {"input_guard": "enforce"}
    assert _run(repo.get(SCOPE_TENANT, "tenant-b")) is None


def test_save_updates_existing_scope_row(session, repo):
    existing = _model()
    session.queue_result([existing])
    _run(
        repo.save(
            GuardSettings(
                scope_kind=SCOPE_TENANT,
                scope_id="tenant-a",
                overrides={"output_guard": "monitor"},
                updated_by="root",
                updated_at=T0,
            )
        )
    )
    sql = session.sql()
    assert "guard_settings.scope_kind = 'tenant'" in sql
    assert "guard_settings.scope_id = 'tenant-a'" in sql
    assert existing.overrides == {"output_guard": "monitor"}
    assert existing.updated_by == "root"
    assert session.added == []
    assert session.commits == 1


def test_save_inserts_new_scope_row(session, repo):
    _run(
        repo.save(
            GuardSettings(scope_kind=SCOPE_PROFILE, scope_id="pro", id="gs-9")
        )
    )
    (m,) = session.added
    assert (m.id, m.scope_kind, m.scope_id, m.overrides) == (
        "gs-9",
        "profile",
        "pro",
        {},
    )


def test_list_profiles_only_profile_scope(session, repo):
    session.queue_result([_model(scope_kind="profile", scope_id="pro", overrides=None)])
    (p,) = _run(repo.list_profiles())
    assert "guard_settings.scope_kind = 'profile'" in session.sql()
    assert p.overrides == {}
