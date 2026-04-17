"""Tool label 解析：統一 tool_name → 顯示 label 的單一來源。

設計動機（Issue #30）：前端 TOOL_LABELS 與後端 BUILT_IN_TOOL_DEFAULTS
各自維護一份 name→label 對應會漂移。統一由 backend 在 tool_calls event
直接帶 label，前端零邏輯即可一致顯示。
"""

from __future__ import annotations

from src.domain.agent.built_in_tool import BUILT_IN_TOOL_DEFAULTS


def resolve_tool_label(
    name: str,
    mcp_tools: dict[str, str] | None = None,
) -> str:
    """解析 tool 顯示 label。優先順序：內建 → MCP → fallback 原名。

    mcp_tools: optional {tool_name: label} mapping（由 MCP registry 組出）
    """
    for t in BUILT_IN_TOOL_DEFAULTS:
        if t.name == name:
            return t.label
    if mcp_tools and name in mcp_tools:
        return mcp_tools[name]
    return name
