"""驗證 BUILT_IN_TOOL_DEFAULTS 常數內容（seed source of truth；DB 由此灌入）。

S-Gov.2: 原本硬編碼在 agent_router.BUILT_IN_TOOLS 的清單已移至
domain/agent/built_in_tool.py 的 BUILT_IN_TOOL_DEFAULTS，作為啟動 seed 來源。
"""

from src.domain.agent.built_in_tool import BUILT_IN_TOOL_DEFAULTS, BuiltInTool


def test_contains_at_least_two_tools():
    assert len(BUILT_IN_TOOL_DEFAULTS) >= 2


def test_all_items_are_built_in_tool():
    for item in BUILT_IN_TOOL_DEFAULTS:
        assert isinstance(item, BuiltInTool)


def test_contains_rag_query():
    names = [t.name for t in BUILT_IN_TOOL_DEFAULTS]
    assert "rag_query" in names


def test_contains_query_dm_with_image():
    names = [t.name for t in BUILT_IN_TOOL_DEFAULTS]
    assert "query_dm_with_image" in names


def test_each_tool_has_required_fields():
    for tool in BUILT_IN_TOOL_DEFAULTS:
        assert tool.name and isinstance(tool.name, str)
        assert tool.label and isinstance(tool.label, str)
        assert tool.description and isinstance(tool.description, str)
        assert isinstance(tool.requires_kb, bool)


def test_tool_names_unique():
    names = [t.name for t in BUILT_IN_TOOL_DEFAULTS]
    assert len(names) == len(set(names))


def test_defaults_scope_is_global():
    """新 tool 預設 scope 為 global（seed 時首次灌入的預設值）"""
    for tool in BUILT_IN_TOOL_DEFAULTS:
        assert tool.scope == "global"
        assert tool.tenant_ids == []
