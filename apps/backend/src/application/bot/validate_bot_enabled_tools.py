"""Validate Bot.enabled_tools against tenant-accessible built-in tools.

只驗證 built-in tool 名稱；非 built-in（如 MCP tool）一律 passthrough，
由 MCP binding 機制自行管控。
"""

from __future__ import annotations

from src.domain.agent.built_in_tool import BuiltInToolRepository


async def validate_bot_enabled_tools(
    *,
    enabled_tools: list[str],
    tenant_id: str,
    built_in_tool_repository: BuiltInToolRepository,
) -> None:
    """
    Raises ValueError if any built-in tool in ``enabled_tools`` is not
    accessible to the given tenant.

    - 以 ``find_all()`` 取得系統所有 built-in tool 名稱（universe）
    - 以 ``find_accessible(tenant_id)`` 取得該租戶可用名稱
    - 傳入 ``enabled_tools`` 中若某名稱屬於 universe 但不在 accessible → reject
    - 其他名稱（不屬 universe）視為 MCP / 自訂 tool，passthrough
    """
    all_tools = await built_in_tool_repository.find_all()
    universe = {t.name for t in all_tools}
    accessible = {
        t.name
        for t in await built_in_tool_repository.find_accessible(tenant_id)
    }

    unauthorized = [
        name
        for name in enabled_tools
        if name in universe and name not in accessible
    ]
    if unauthorized:
        raise ValueError(
            "Unauthorized built-in tools for tenant "
            f"{tenant_id}: {', '.join(unauthorized)}"
        )
