"""SQLAlchemyApiKeyRepository — 租戶過濾條件與實體映射（Issue #101）。

find_by_id 不帶租戶：它是 client_credentials 驗證入口（client_id 即 id），
呼叫端以 key.tenant_id 決定簽發對象；管理端點以 tenant 比對擋跨租戶。
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from src.domain.auth.api_key import ApiKey
from src.infrastructure.db.models.api_key_model import ApiKeyModel
from src.infrastructure.db.repositories.api_key_repository import (
    SQLAlchemyApiKeyRepository,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


def _model(**over) -> ApiKeyModel:
    data: dict = {
        "id": "key-1",
        "tenant_id": "tenant-a",
        "name": "erp",
        "description": "",
        "secret_hash": "h" * 64,
        "secret_salt": "s" * 32,
        "secret_prefix": "sk_abcd",
        "scopes": None,
        "allowed_bot_ids": ["bot-1"],
        "expires_at": None,
        "revoked_at": T0,
        "token_version": 2,
        "last_used_at": None,
        "created_by": "u-1",
        "created_at": T0,
        "updated_at": T0,
    }
    data.update(over)
    return ApiKeyModel(**data)


def _key(**over) -> ApiKey:
    data: dict = {
        "id": "key-1",
        "tenant_id": "tenant-a",
        "name": "erp2",
        "secret_hash": "H" * 64,
        "secret_salt": "S" * 32,
        "secret_prefix": "sk_new",
        "scopes": ["chat"],
        "allowed_bot_ids": [],
        "token_version": 3,
    }
    data.update(over)
    return ApiKey(**data)


@pytest.fixture
def session() -> SpySession:
    return SpySession()


@pytest.fixture
def repo(session) -> SQLAlchemyApiKeyRepository:
    return SQLAlchemyApiKeyRepository(session)  # type: ignore[arg-type]


def test_list_by_tenant_filters_tenant_and_maps(session, repo):
    session.queue_result([_model()])
    (key,) = _run(repo.list_by_tenant("tenant-a"))
    assert "api_keys.tenant_id = 'tenant-a'" in session.sql(0)
    assert key.tenant_id == "tenant-a"
    assert key.scopes == []
    assert key.allowed_bot_ids == ["bot-1"]
    assert key.revoked_at == T0
    assert key.token_version == 2
    assert key.secret_hash == "h" * 64


def test_list_all_is_unscoped(session, repo):
    _run(repo.list_all())
    assert "WHERE" not in session.sql(0)


def test_find_by_id(session, repo):
    assert _run(repo.find_by_id("x")) is None
    session.get_result = _model()
    key = _run(repo.find_by_id("key-1"))
    assert key is not None and key.tenant_id == "tenant-a"


def test_save_new_adds_model(session, repo):
    _run(repo.save(_key()))
    (added,) = session.added
    assert isinstance(added, ApiKeyModel)
    assert (added.tenant_id, added.secret_prefix) == ("tenant-a", "sk_new")
    assert added.scopes == ["chat"]


def test_save_existing_updates_mutable_fields_only(session, repo):
    existing = _model()
    session.get_result = existing
    _run(repo.save(_key(tenant_id="tenant-b")))
    assert session.added == []
    assert existing.name == "erp2"
    assert existing.scopes == ["chat"]
    assert existing.token_version == 3
    # 租戶與密鑰雜湊不可經 save 改寫
    assert existing.tenant_id == "tenant-a"
    assert existing.secret_hash == "h" * 64


def test_touch_last_used(session, repo):
    _run(repo.touch_last_used("key-1", T0))
    sql = session.sql(0)
    assert sql.startswith("UPDATE api_keys")
    assert "api_keys.id = 'key-1'" in sql
    assert "last_used_at=" in sql
