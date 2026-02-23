"""WorkerContext 擴展 BDD Step Definitions"""

import pytest
from pytest_bdd import given, scenarios, then

from src.domain.agent.worker import WorkerContext

scenarios("unit/agent/worker_context_expansion.feature")


@pytest.fixture
def context():
    return {}


@given("建立一個未指定角色的 WorkerContext")
def create_default_context(context):
    context["wc"] = WorkerContext(
        tenant_id="tenant-001",
        kb_id="kb-001",
        user_message="你好",
    )


@given("建立一個 marketing 角色的 WorkerContext")
def create_marketing_context(context):
    context["wc"] = WorkerContext(
        tenant_id="tenant-001",
        kb_id="kb-001",
        user_message="建立活動",
        user_role="marketing",
    )


@given("權限包含 \"campaign:create\" 和 \"campaign:read\"")
def set_permissions(context):
    context["wc"].user_permissions = ["campaign:create", "campaign:read"]


@given("建立一個帶有 MCP 工具的 WorkerContext")
def create_mcp_context(context):
    context["wc"] = WorkerContext(
        tenant_id="tenant-001",
        kb_id="kb-001",
        user_message="搜尋知識庫",
    )


@given("MCP 工具包含 \"knowledge_search\" 和 \"order_lookup\"")
def set_mcp_tools(context):
    context["wc"].mcp_tools = {
        "knowledge_search": {"description": "搜尋知識庫"},
        "order_lookup": {"description": "訂單查詢"},
    }


@then("user_role 應為 \"customer\"")
def verify_default_role(context):
    assert context["wc"].user_role == "customer"


@then("user_role 應為 \"marketing\"")
def verify_marketing_role(context):
    assert context["wc"].user_role == "marketing"


@then("user_permissions 應為空列表")
def verify_empty_permissions(context):
    assert context["wc"].user_permissions == []


@then("user_permissions 應包含 \"campaign:create\"")
def verify_has_create(context):
    assert "campaign:create" in context["wc"].user_permissions


@then("user_permissions 應包含 \"campaign:read\"")
def verify_has_read(context):
    assert "campaign:read" in context["wc"].user_permissions


@then("mcp_tools 應為空字典")
def verify_empty_mcp_tools(context):
    assert context["wc"].mcp_tools == {}


@then("mcp_tools 應包含 \"knowledge_search\" 鍵")
def verify_has_knowledge_search(context):
    assert "knowledge_search" in context["wc"].mcp_tools


@then("mcp_tools 應包含 \"order_lookup\" 鍵")
def verify_has_order_lookup(context):
    assert "order_lookup" in context["wc"].mcp_tools
