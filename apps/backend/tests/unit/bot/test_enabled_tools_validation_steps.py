"""Bot enabled_tools 權限驗證 BDD Step Definitions."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.bot.validate_bot_enabled_tools import (
    validate_bot_enabled_tools,
)
from src.domain.agent.built_in_tool import BuiltInTool, BuiltInToolRepository

scenarios("unit/bot/enabled_tools_validation.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def accessible_store() -> dict[str, list[BuiltInTool]]:
    return {}


@pytest.fixture
def mock_repo(accessible_store):
    """find_accessible returns per-tenant list from store;
    find_all returns union (for built-in name universe)."""
    repo = AsyncMock(spec=BuiltInToolRepository)

    async def _find_accessible(tenant_id: str):
        return list(accessible_store.get(tenant_id, []))

    async def _find_all():
        seen: dict[str, BuiltInTool] = {}
        # Union all tenants + include the three hardcoded built-in names so
        # validate_bot_enabled_tools can distinguish "unknown built-in" from
        # "MCP / passthrough". We represent universe via a fixed list.
        for tools in accessible_store.values():
            for t in tools:
                seen[t.name] = t
        # Ensure canonical built-in names are part of the universe
        for canonical in ("rag_query", "query_dm_with_image", "transfer_to_human_agent"):
            seen.setdefault(
                canonical,
                BuiltInTool(name=canonical, label=canonical, description=""),
            )
        return list(seen.values())

    repo.find_accessible = AsyncMock(side_effect=_find_accessible)
    repo.find_all = AsyncMock(side_effect=_find_all)
    return repo


@pytest.fixture
def context():
    return {}


@given(parsers.parse('租戶 "{tenant_id}" 可存取的 built-in tools 為 "{names_csv}"'))
def given_accessible(accessible_store, tenant_id, names_csv):
    names = [n.strip() for n in names_csv.split(",") if n.strip()]
    accessible_store[tenant_id] = [
        BuiltInTool(name=n, label=n, description="") for n in names
    ]


@when(
    parsers.parse(
        '我以租戶 "{tenant_id}" 驗證 enabled_tools "{tools_csv}"'
    )
)
def do_validate(context, mock_repo, tenant_id, tools_csv):
    enabled = [n.strip() for n in tools_csv.split(",") if n.strip()]
    try:
        _run(
            validate_bot_enabled_tools(
                enabled_tools=enabled,
                tenant_id=tenant_id,
                built_in_tool_repository=mock_repo,
            )
        )
        context["error"] = None
    except ValueError as exc:
        context["error"] = str(exc)


@then(parsers.parse('應拋出驗證錯誤且訊息包含 "{substr}"'))
def check_error_contains(context, substr):
    assert context["error"] is not None, "expected ValueError but none raised"
    assert substr in context["error"], (
        f"expected '{substr}' in error message: {context['error']}"
    )


@then("驗證應通過")
def check_no_error(context):
    assert context["error"] is None, f"unexpected error: {context['error']}"
