"""SQLAlchemyBuiltInToolRepository — 租戶可見性過濾與 seed 冪等（Issue #101）。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import pytest

from src.domain.agent.built_in_tool import BuiltInTool
from src.infrastructure.db.models.built_in_tool_model import BuiltInToolModel
from src.infrastructure.db.repositories.built_in_tool_repository import (
    SQLAlchemyBuiltInToolRepository,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


class _KeyedGetSession(SpySession):
    """session.get 依主鍵回傳不同物件（seed 多筆時需要）。"""

    def __init__(self) -> None:
        super().__init__()
        self.rows: dict[Any, Any] = {}

    async def get(self, model: Any, pk: Any, *args: Any, **kwargs: Any) -> Any:
        return self.rows.get(pk)


def _run(coro):
    return asyncio.run(coro)


def _model(**over) -> BuiltInToolModel:
    data: dict = {
        "name": "rag_query",
        "label": "知識庫",
        "description": None,
        "requires_kb": None,
        "scope": None,
        "tenant_ids": None,
        "created_at": T0,
        "updated_at": T0,
    }
    data.update(over)
    return BuiltInToolModel(**data)


@pytest.fixture
def session() -> _KeyedGetSession:
    return _KeyedGetSession()


@pytest.fixture
def repo(session) -> SQLAlchemyBuiltInToolRepository:
    return SQLAlchemyBuiltInToolRepository(session)  # type: ignore[arg-type]


def test_find_accessible_is_global_or_tenant_listed(session, repo):
    session.queue_result([_model()])
    (tool,) = _run(repo.find_accessible("tenant-a"))
    # JSONB 參數無法內嵌字面值 → 以參數化 SQL + 綁定值斷言
    sql = session.sql()
    params = session.statements[-1].compile().params
    assert "built_in_tools.scope = " in sql
    assert "CAST(built_in_tools.tenant_ids AS JSONB) @>" in sql
    assert "global" in params.values()
    assert ["tenant-a"] in params.values()
    # None 欄位落回預設
    assert (tool.scope, tool.tenant_ids, tool.requires_kb) == ("global", [], False)
    assert tool.description == ""


def test_find_all_and_by_name(session, repo):
    session.queue_result([_model(), _model(name="transfer")])
    assert [t.name for t in _run(repo.find_all())] == ["rag_query", "transfer"]
    assert "WHERE" not in session.sql()

    session.rows["rag_query"] = _model(scope="tenant", tenant_ids=["t1"])
    t = _run(repo.find_by_name("rag_query"))
    assert (t.scope, t.tenant_ids) == ("tenant", ["t1"])
    assert _run(repo.find_by_name("none")) is None


def test_upsert_insert_and_update(session, repo):
    tool = BuiltInTool(
        name="new", label="L", description="d", scope="tenant", tenant_ids=["t1"]
    )
    _run(repo.upsert(tool))
    (m,) = session.added
    assert (m.scope, m.tenant_ids) == ("tenant", ["t1"])

    existing = _model()
    session.rows["rag_query"] = existing
    _run(
        repo.upsert(
            BuiltInTool(
                name="rag_query", label="L2", description="", scope="tenant",
                tenant_ids=["t2"],
            )
        )
    )
    assert (existing.label, existing.scope, existing.tenant_ids) == (
        "L2",
        "tenant",
        ["t2"],
    )


def test_seed_defaults_preserves_admin_scope(session, repo):
    existing = _model(scope="tenant", tenant_ids=["t1"])
    session.rows["rag_query"] = existing
    _run(
        repo.seed_defaults(
            [
                BuiltInTool(name="rag_query", label="新標籤", description="新描述"),
                BuiltInTool(name="fresh", label="F", description="x", requires_kb=True),
            ]
        )
    )
    # 既有：只更新顯示欄位，保留管理員設定的可見範圍
    assert (existing.label, existing.description) == ("新標籤", "新描述")
    assert (existing.scope, existing.tenant_ids) == ("tenant", ["t1"])
    (added,) = session.added
    assert (added.name, added.requires_kb, added.scope) == ("fresh", True, "global")
