"""TenantIdentitySecret repository — 以 tenant_id 為主鍵、只存加密值（Issue #101）。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import pytest

from src.domain.widget.identity import TenantIdentitySecret
from src.infrastructure.db.models.tenant_identity_secret_model import (
    TenantIdentitySecretModel,
)
from src.infrastructure.db.repositories.tenant_identity_secret_repository import (
    SQLAlchemyTenantIdentitySecretRepository,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)
T1 = datetime(2026, 9, 2, tzinfo=timezone.utc)


class _KeyedGetSession(SpySession):
    """記下 session.get 的主鍵，並依主鍵回傳資料列。"""

    def __init__(self) -> None:
        super().__init__()
        self.rows: dict[Any, Any] = {}
        self.get_keys: list[Any] = []

    async def get(self, model: Any, pk: Any, *args: Any, **kwargs: Any) -> Any:
        self.get_keys.append(pk)
        return self.rows.get(pk)


def _run(coro):
    return asyncio.run(coro)


def _model(**over) -> TenantIdentitySecretModel:
    data: dict = {
        "tenant_id": "tenant-a",
        "secret_encrypted": "enc:aaa",
        "is_enabled": True,
        "enforce_verified": False,
        "rotated_at": T0,
        "updated_at": T0,
    }
    data.update(over)
    return TenantIdentitySecretModel(**data)


@pytest.fixture
def session() -> _KeyedGetSession:
    return _KeyedGetSession()


@pytest.fixture
def repo(session) -> SQLAlchemyTenantIdentitySecretRepository:
    return SQLAlchemyTenantIdentitySecretRepository(session)  # type: ignore[arg-type]


def test_get_is_keyed_by_tenant(session, repo):
    session.rows["tenant-a"] = _model()
    s = _run(repo.get("tenant-a"))
    assert session.get_keys == ["tenant-a"]
    assert s is not None
    assert (s.tenant_id, s.secret_encrypted, s.enforce_verified) == (
        "tenant-a",
        "enc:aaa",
        False,
    )
    assert _run(repo.get("tenant-b")) is None  # 他租戶沒有就是沒有


def test_save_inserts_encrypted_value(session, repo):
    new = TenantIdentitySecret(tenant_id="tenant-b", secret_encrypted="enc:b")
    _run(repo.save(new))
    (m,) = session.added
    assert (m.tenant_id, m.secret_encrypted) == ("tenant-b", "enc:b")
    assert session.get_keys == ["tenant-b"]


def test_save_rotates_existing_row(session, repo):
    existing = _model()
    session.rows["tenant-a"] = existing
    _run(
        repo.save(
            TenantIdentitySecret(
                tenant_id="tenant-a",
                secret_encrypted="enc:new",
                is_enabled=False,
                enforce_verified=True,
                rotated_at=T1,
                updated_at=T1,
            )
        )
    )
    assert session.added == []
    assert existing.secret_encrypted == "enc:new"
    assert (existing.is_enabled, existing.enforce_verified) == (False, True)
    assert existing.rotated_at == T1
