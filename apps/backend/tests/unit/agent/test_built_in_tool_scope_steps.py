"""Built-in Tool Tenant Scope BDD Step Definitions."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.agent.list_built_in_tools_use_case import (
    ListBuiltInToolsUseCase,
)
from src.domain.agent.built_in_tool import BuiltInTool, BuiltInToolRepository

scenarios("unit/agent/built_in_tool_scope.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Shared in-memory store + mock repo
# ---------------------------------------------------------------------------


@pytest.fixture
def tools_store() -> dict[str, BuiltInTool]:
    """Shared dict keyed by tool name, simulates DB state."""
    return {}


@pytest.fixture
def mock_repo(tools_store):
    repo = AsyncMock(spec=BuiltInToolRepository)

    async def _find_all():
        return list(tools_store.values())

    async def _find_accessible(tenant_id: str):
        return [t for t in tools_store.values() if t.is_accessible_by(tenant_id)]

    async def _find_by_name(name: str):
        return tools_store.get(name)

    async def _upsert(tool: BuiltInTool):
        tools_store[tool.name] = tool

    async def _seed_defaults(defaults):
        for d in defaults:
            existing = tools_store.get(d.name)
            if existing is None:
                tools_store[d.name] = d
            else:
                # keep existing scope/tenant_ids, refresh metadata
                existing.label = d.label
                existing.description = d.description
                existing.requires_kb = d.requires_kb

    repo.find_all = AsyncMock(side_effect=_find_all)
    repo.find_accessible = AsyncMock(side_effect=_find_accessible)
    repo.find_by_name = AsyncMock(side_effect=_find_by_name)
    repo.upsert = AsyncMock(side_effect=_upsert)
    repo.seed_defaults = AsyncMock(side_effect=_seed_defaults)
    return repo


@pytest.fixture
def use_case(mock_repo):
    return ListBuiltInToolsUseCase(repository=mock_repo)


@pytest.fixture
def context():
    return {}


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given(parsers.parse('一個 "{scope}" scope 的工具 "{name}"'))
def given_global_tool(tools_store, scope, name):
    tools_store[name] = BuiltInTool(
        name=name,
        label=f"{name}_label",
        description="",
        scope=scope,
        tenant_ids=[],
    )


@given(
    parsers.parse(
        '一個 "{scope}" scope 的工具 "{name}" 白名單為 "{tenant_id}"'
    )
)
def given_tenant_tool(tools_store, scope, name, tenant_id):
    tools_store[name] = BuiltInTool(
        name=name,
        label=f"{name}_label",
        description="",
        scope=scope,
        tenant_ids=[tenant_id],
    )


@given(parsers.parse("系統內已註冊 {count:d} 個 built-in tool"))
def given_n_tools(tools_store, count):
    for i in range(count):
        name = f"tool_{i}"
        tools_store[name] = BuiltInTool(
            name=name,
            label=f"label_{i}",
            description="",
            scope="global",
            tenant_ids=[],
        )


@given(
    parsers.parse(
        'DB 已有工具 "{name}" scope 為 "{scope}" 且白名單為 "{tenant_id}"'
    )
)
def given_db_tool(tools_store, name, scope, tenant_id):
    tools_store[name] = BuiltInTool(
        name=name,
        label="OLD_LABEL",
        description="OLD_DESC",
        scope=scope,
        tenant_ids=[tenant_id],
    )


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when(parsers.parse('租戶 "{tenant_id}" 查詢可用工具'))
def tenant_list_tools(context, use_case, tenant_id):
    context["result"] = _run(
        use_case.execute(tenant_id=tenant_id, is_admin=False)
    )


@when("系統管理員查詢工具清單")
def admin_list_tools(context, use_case):
    context["result"] = _run(use_case.execute(tenant_id=None, is_admin=True))


@when("應用啟動執行 seed_defaults")
def run_seed(mock_repo):
    defaults = [
        BuiltInTool(
            name="rag_query",
            label="知識庫查詢",
            description="NEW_DESC",
            requires_kb=True,
        ),
    ]
    _run(mock_repo.seed_defaults(defaults))


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then(parsers.parse('結果應包含 "{name}"'))
def result_contains(context, name):
    names = [t.name for t in context["result"]]
    assert name in names, f"expected {name} in {names}"


@then(parsers.parse('結果不應包含 "{name}"'))
def result_not_contains(context, name):
    names = [t.name for t in context["result"]]
    assert name not in names, f"unexpected {name} in {names}"


@then(parsers.parse("結果應包含 {count:d} 個工具且每個都帶 scope 欄位"))
def result_count_with_scope(context, count):
    assert len(context["result"]) == count
    for t in context["result"]:
        assert t.scope in {"global", "tenant"}


@then(parsers.parse('"{name}" 的 scope 仍為 "{scope}"'))
def scope_unchanged(tools_store, name, scope):
    assert tools_store[name].scope == scope


@then(parsers.parse('"{name}" 的白名單仍為 "{tenant_id}"'))
def tenant_ids_unchanged(tools_store, name, tenant_id):
    assert tools_store[name].tenant_ids == [tenant_id]


@then(parsers.parse('"{name}" 的 label 更新為最新預設值'))
def label_updated(tools_store, name):
    assert tools_store[name].label != "OLD_LABEL"
