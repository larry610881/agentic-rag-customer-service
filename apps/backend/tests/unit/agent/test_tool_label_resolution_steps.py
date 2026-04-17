"""Tool label 解析 BDD Step Definitions"""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.agent.tool_label_resolver import resolve_tool_label

scenarios("unit/agent/tool_label_resolution.feature")


@pytest.fixture
def context():
    return {}


@given(parsers.parse('內建工具清單包含 "{name}" 對應 "{label}"'))
def builtin_contains(context, name, label):
    # 此 scenario 直接驗證 resolve_tool_label 吃預設 BUILT_IN_TOOL_DEFAULTS，
    # assertion 階段再檢查實際 mapping
    context.setdefault("expect", {})[name] = label


@given(parsers.parse('內建工具清單不含 "{name}"'))
def builtin_excludes(context, name):
    context.setdefault("unknown_name", name)


@given(parsers.parse(
    'MCP registry 含工具 "{name}" 對應 label "{label}"'
))
def mcp_registry_has(context, name, label):
    context.setdefault("mcp_tools", {})[name] = label


@given(parsers.parse('MCP registry 也不含 "{name}"'))
def mcp_registry_lacks(context, name):
    context.setdefault("mcp_tools", {})


@when(parsers.parse('呼叫 resolve_tool_label("{name}")'))
def call_resolve(context, name):
    context["result"] = resolve_tool_label(name, mcp_tools=context.get("mcp_tools"))


@when(parsers.parse('呼叫 resolve_tool_label("{name}") 並附上 registry'))
def call_resolve_with_registry(context, name):
    context["result"] = resolve_tool_label(name, mcp_tools=context.get("mcp_tools"))


@then(parsers.parse('應回傳 "{expected}"'))
def verify_result(context, expected):
    assert context["result"] == expected
