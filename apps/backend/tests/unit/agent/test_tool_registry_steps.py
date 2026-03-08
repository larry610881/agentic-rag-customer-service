"""Tool Registry BDD Step Definitions"""

from unittest.mock import MagicMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.agent.tool_registry import ToolRegistry

scenarios("unit/agent/tool_registry.feature")


@pytest.fixture
def context():
    return {}


# --- Given ---


@given("一個空的 ToolRegistry")
def empty_registry(context):
    context["registry"] = ToolRegistry()


@given('一個包含 "rag_query" 和 "query_products" 的 ToolRegistry')
def registry_with_two_tools(context):
    registry = ToolRegistry()
    registry.register("rag_query", "查詢知識庫")
    registry.register("query_products", "查詢商品")
    context["registry"] = registry


@given('一個包含 "rag_query" 的 ToolRegistry')
def registry_with_rag(context):
    registry = ToolRegistry()
    mock_tool = MagicMock()
    mock_tool.name = "rag_query"
    registry.register("rag_query", "查詢知識庫", lc_tool=mock_tool)
    context["registry"] = registry


# --- When ---


@when('註冊工具 "rag_query" 描述為 "查詢知識庫"')
def register_rag(context):
    context["registry"].register("rag_query", "查詢知識庫")


@when('註冊工具 "query_products" 描述為 "查詢商品"')
def register_products(context):
    context["registry"].register("query_products", "查詢商品")


@when('以 ["rag_query"] 篩選 get_descriptions')
def filter_descriptions(context):
    context["result"] = context["registry"].get_descriptions(["rag_query"])


@when('註冊工具 "rag_query" 並附帶 LangChain 工具實例')
def register_with_lc_tool(context):
    mock_tool = MagicMock()
    mock_tool.name = "rag_query"
    context["registry"].register("rag_query", "查詢知識庫", lc_tool=mock_tool)


@when('以 ["not_exist"] 篩選 get_tools')
def filter_tools_not_exist(context):
    context["result"] = context["registry"].get_tools(["not_exist"])


# --- Then ---


@then("get_descriptions 應回傳 2 個工具描述")
def verify_two_descriptions(context):
    descs = context["registry"].get_descriptions()
    assert len(descs) == 2


@then('"rag_query" 的描述應為 "查詢知識庫"')
def verify_rag_description(context):
    descs = context["registry"].get_descriptions()
    assert descs["rag_query"] == "查詢知識庫"


@then("應只回傳 1 個工具描述")
def verify_one_description(context):
    assert len(context["result"]) == 1


@then("get_tools 應回傳 1 個工具實例")
def verify_one_tool(context):
    tools = context["registry"].get_tools()
    assert len(tools) == 1


@then("應回傳空的工具列表")
def verify_empty_tools(context):
    assert context["result"] == []
