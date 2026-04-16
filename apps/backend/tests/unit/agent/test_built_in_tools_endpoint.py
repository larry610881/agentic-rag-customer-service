"""驗證 BUILT_IN_TOOLS 常數內容（agent_router endpoint 直接回此 list）。"""

from src.interfaces.api.agent_router import BUILT_IN_TOOLS, BuiltInToolItem


def test_contains_at_least_two_tools():
    assert len(BUILT_IN_TOOLS) >= 2


def test_all_items_are_built_in_tool_item():
    for item in BUILT_IN_TOOLS:
        assert isinstance(item, BuiltInToolItem)


def test_contains_rag_query():
    names = [t.name for t in BUILT_IN_TOOLS]
    assert "rag_query" in names


def test_contains_query_dm_with_image():
    names = [t.name for t in BUILT_IN_TOOLS]
    assert "query_dm_with_image" in names


def test_each_tool_has_required_fields():
    for tool in BUILT_IN_TOOLS:
        assert tool.name and isinstance(tool.name, str)
        assert tool.label and isinstance(tool.label, str)
        assert tool.description and isinstance(tool.description, str)
        assert isinstance(tool.requires_kb, bool)


def test_tool_names_unique():
    names = [t.name for t in BUILT_IN_TOOLS]
    assert len(names) == len(set(names))
