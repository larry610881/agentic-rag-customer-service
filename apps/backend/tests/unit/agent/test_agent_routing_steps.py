"""Agent 路由 BDD Step Definitions"""

import asyncio

import pytest
from pytest_bdd import given, scenarios, then, when

from src.infrastructure.langgraph.fake_agent_service import FakeAgentService

scenarios("unit/agent/agent_routing.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


@given("Agent 服務已初始化")
def agent_initialized(context):
    context["agent"] = FakeAgentService()
    context["tenant_id"] = "tenant-001"
    context["kb_id"] = "kb-001"


@when('用戶發送訊息 "我的訂單 ORD-001 到哪了"')
def send_order_message(context):
    context["response"] = _run(
        context["agent"].process_message(
            tenant_id=context["tenant_id"],
            kb_id=context["kb_id"],
            user_message="我的訂單 ORD-001 到哪了",
        )
    )


@when('用戶發送訊息 "有什麼電子產品"')
def send_product_message(context):
    context["response"] = _run(
        context["agent"].process_message(
            tenant_id=context["tenant_id"],
            kb_id=context["kb_id"],
            user_message="有什麼電子產品",
        )
    )


@when('用戶發送訊息 "退貨政策是什麼"')
def send_rag_message(context):
    context["response"] = _run(
        context["agent"].process_message(
            tenant_id=context["tenant_id"],
            kb_id=context["kb_id"],
            user_message="退貨政策是什麼",
        )
    )


@when('用戶發送訊息 "我要投訴"')
def send_ticket_message(context):
    context["response"] = _run(
        context["agent"].process_message(
            tenant_id=context["tenant_id"],
            kb_id=context["kb_id"],
            user_message="我要投訴",
        )
    )


@then('Agent 應選擇 "order_lookup" 工具')
def verify_order_tool(context):
    assert context["response"].tool_calls[0]["tool_name"] == "order_lookup"


@then('Agent 應選擇 "product_search" 工具')
def verify_product_tool(context):
    assert context["response"].tool_calls[0]["tool_name"] == "product_search"


@then('Agent 應選擇 "rag_query" 工具')
def verify_rag_tool(context):
    assert context["response"].tool_calls[0]["tool_name"] == "rag_query"


@then('Agent 應選擇 "ticket_creation" 工具')
def verify_ticket_tool(context):
    assert context["response"].tool_calls[0]["tool_name"] == "ticket_creation"


@then("回應應包含工具調用記錄")
def verify_has_tool_calls(context):
    assert len(context["response"].tool_calls) > 0


@then("工具調用記錄應包含選擇理由")
def verify_has_reasoning(context):
    assert context["response"].tool_calls[0]["reasoning"] != ""
