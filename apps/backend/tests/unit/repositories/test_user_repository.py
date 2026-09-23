"""SQLAlchemyUserRepository — 租戶過濾條件與實體映射（Issue #101）。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from src.domain.auth.entity import User
from src.domain.auth.value_objects import Email, Role, UserId
from src.infrastructure.db.models.user_model import UserModel
from src.infrastructure.db.repositories.user_repository import (
    SQLAlchemyUserRepository,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


def _model(**over) -> UserModel:
    data: dict = {
        "id": "u-1",
        "tenant_id": "tenant-a",
        "email": "a@example.com",
        "hashed_password": "hash",
        "role": "tenant_admin",
        "token_version": 3,
        "created_at": T0,
        "updated_at": T0,
    }
    data.update(over)
    return UserModel(**data)


def _user(**over) -> User:
    data: dict = {
        "id": UserId(value="u-1"),
        "tenant_id": "tenant-a",
        "email": Email("a@example.com"),
        "hashed_password": "new-hash",
        "role": Role.USER,
        "token_version": 4,
    }
    data.update(over)
    return User(**data)


@pytest.fixture
def session() -> SpySession:
    return SpySession()


@pytest.fixture
def repo(session) -> SQLAlchemyUserRepository:
    return SQLAlchemyUserRepository(session)  # type: ignore[arg-type]


def test_find_by_id_maps_entity(session, repo):
    assert _run(repo.find_by_id("u-1")) is None
    session.get_result = _model()
    user = _run(repo.find_by_id("u-1"))
    assert user is not None
    assert user.id.value == "u-1"
    assert user.tenant_id == "tenant-a"
    assert user.email.value == "a@example.com"
    assert user.role is Role.TENANT_ADMIN
    assert user.token_version == 3


def test_find_by_email(session, repo):
    assert _run(repo.find_by_email("x@example.com")) is None
    session.queue_result([_model()])
    user = _run(repo.find_by_email("a@example.com"))
    assert "users.email = 'a@example.com'" in session.sql(-1)
    assert user is not None and user.hashed_password == "hash"


def test_find_all_by_tenant_filters_tenant(session, repo):
    session.queue_result([_model()])
    (user,) = _run(repo.find_all_by_tenant("tenant-a", limit=10, offset=10))
    sql = session.sql(0)
    assert "users.tenant_id = 'tenant-a'" in sql
    assert "LIMIT 10" in sql and "OFFSET 10" in sql
    assert user.tenant_id == "tenant-a"


def test_find_all_with_and_without_tenant(session, repo):
    _run(repo.find_all(tenant_id="tenant-a", limit=1, offset=2))
    sql = session.sql(0)
    assert "users.tenant_id = 'tenant-a'" in sql
    assert "LIMIT 1" in sql and "OFFSET 2" in sql
    _run(repo.find_all())  # system_admin 列表
    assert "WHERE" not in session.sql(-1)


def test_count_all(session, repo):
    session.queue_result([5])
    assert _run(repo.count_all(tenant_id="tenant-a")) == 5
    assert "users.tenant_id = 'tenant-a'" in session.sql(0)
    _run(repo.count_all())
    assert "WHERE" not in session.sql(-1)


def test_find_admin_email_by_tenant(session, repo):
    session.queue_result(["admin@example.com"])
    assert _run(repo.find_admin_email_by_tenant("tenant-a")) == "admin@example.com"
    sql = session.sql(0)
    assert "users.tenant_id = 'tenant-a'" in sql
    assert "users.role = 'tenant_admin'" in sql
    assert "LIMIT 1" in sql


def test_save_new_user_adds_model(session, repo):
    _run(repo.save(_user()))
    (added,) = session.added
    assert isinstance(added, UserModel)
    assert (added.id, added.tenant_id, added.role) == ("u-1", "tenant-a", "user")
    assert added.token_version == 4
    assert session.commits == 1


def test_save_existing_user_updates_fields(session, repo):
    existing = _model()
    session.get_result = existing
    _run(repo.save(_user(role=Role.TENANT_ADMIN)))
    assert session.added == []
    assert existing.hashed_password == "new-hash"
    assert existing.token_version == 4
    assert existing.role == "tenant_admin"
    assert existing.updated_at > T0


def test_delete(session, repo):
    _run(repo.delete("u-1"))
    sql = session.sql(0)
    assert sql.startswith("DELETE FROM users") and "users.id = 'u-1'" in sql
