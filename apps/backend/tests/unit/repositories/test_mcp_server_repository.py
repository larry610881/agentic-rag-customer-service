"""SQLAlchemyMcpServerRepository — 可存取範圍條件與實體映射（Issue #101）。

MCP server 是平台層級註冊表；租戶只能看到 global 或 tenant_ids 含自己的。
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from src.domain.platform.entity import McpServerRegistration
from src.domain.platform.value_objects import McpRegistryId, McpRegistryToolMeta
from src.infrastructure.db.models.mcp_server_model import McpServerModel
from src.infrastructure.db.repositories.mcp_server_repository import (
    SQLAlchemyMcpServerRepository,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


def _model(**over) -> McpServerModel:
    data: dict = {
        "id": "mcp-1",
        "name": "查訂單",
        "description": None,
        "transport": None,
        "url": "https://mcp.example.com",
        "command": None,
        "args": None,
        "required_env": ["API_KEY"],
        "available_tools": [{"name": "get_order", "description": "查"}, {}],
        "version": None,
        "scope": None,
        "tenant_ids": ["tenant-a"],
        "is_enabled": True,
        "created_at": T0,
        "updated_at": T0,
    }
    data.update(over)
    return McpServerModel(**data)


def _entity(**over) -> McpServerRegistration:
    data: dict = {
        "id": McpRegistryId(value="mcp-1"),
        "name": "新名",
        "url": "https://mcp.example.com",
        "available_tools": [McpRegistryToolMeta(name="t", description="d")],
        "scope": "tenant",
        "tenant_ids": ["tenant-a", "tenant-b"],
        "is_enabled": False,
    }
    data.update(over)
    return McpServerRegistration(**data)


@pytest.fixture
def session() -> SpySession:
    return SpySession()


@pytest.fixture
def repo(session) -> SQLAlchemyMcpServerRepository:
    return SQLAlchemyMcpServerRepository(session)  # type: ignore[arg-type]


def test_find_accessible_requires_enabled_and_global_or_tenant(session, repo):
    session.queue_result([_model()])
    (srv,) = _run(repo.find_accessible("tenant-a"))
    sql = session.sql(0)
    assert "mcp_server_registrations.is_enabled IS true" in sql
    assert "mcp_server_registrations.scope =" in sql
    assert "@>" in sql  # JSONB contains [tenant_id]
    stmt = session.statements[0]
    params = stmt.compile().params
    assert ["tenant-a"] in params.values()
    assert "global" in params.values()
    # 映射
    assert srv.id.value == "mcp-1"
    assert srv.description == "" and srv.transport == "http"
    assert srv.command == "" and srv.args == [] and srv.version == ""
    assert srv.scope == "global"
    assert srv.tenant_ids == ["tenant-a"]
    assert [(t.name, t.description) for t in srv.available_tools] == [
        ("get_order", "查"), ("", "")
    ]


def test_find_by_id_and_by_url(session, repo):
    assert _run(repo.find_by_id("x")) is None
    session.queue_result([_model()])
    assert _run(repo.find_by_id("mcp-1")) is not None
    assert "mcp_server_registrations.id = 'mcp-1'" in session.sql(-1)
    session.queue_result([_model()])
    srv = _run(repo.find_by_url("https://mcp.example.com"))
    assert "mcp_server_registrations.url = 'https://mcp.example.com'" in session.sql(-1)
    assert srv is not None
    assert _run(repo.find_by_url("https://none")) is None


def test_find_all(session, repo):
    session.queue_result([_model(), _model(id="mcp-2")])
    assert [s.id.value for s in _run(repo.find_all())] == ["mcp-1", "mcp-2"]


def test_save_new_adds_model(session, repo):
    _run(repo.save(_entity()))
    (added,) = session.added
    assert isinstance(added, McpServerModel)
    assert added.tenant_ids == ["tenant-a", "tenant-b"]
    assert added.available_tools == [{"name": "t", "description": "d"}]
    assert session.commits == 1


def test_save_existing_updates(session, repo):
    existing = _model()
    session.get_result = existing
    _run(repo.save(_entity()))
    assert session.added == []
    assert existing.name == "新名"
    assert existing.scope == "tenant"
    assert existing.tenant_ids == ["tenant-a", "tenant-b"]
    assert existing.is_enabled is False


def test_delete(session, repo):
    _run(repo.delete("x"))
    assert session.deleted == []
    existing = _model()
    session.get_result = existing
    _run(repo.delete("mcp-1"))
    assert session.deleted == [existing]
