"""Agent 場景 BDD Step Definitions"""

import asyncio

import pytest
from pytest_bdd import given, scenarios, then, when

from src.infrastructure.langgraph.fake_agent_service import FakeAgentService

scenarios("unit/agent/agent_scenarios.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


@given("Agent 服務已準備好處理知識查詢")
def agent_ready_rag(context):
    context["agent"] = FakeAgentService()
    context["tenant_id"] = "tenant-001"
    context["kb_id"] = "kb-001"


@when('用戶查詢 "退貨政策是什麼"')
def query_rag(context):
    context["response"] = _run(
        context["agent"].process_message(
            tenant_id=context["tenant_id"],
            kb_id=context["kb_id"],
            user_message="退貨政策是什麼",
        )
    )


@when('用戶查詢 "保固政策說明"')
def query_warranty(context):
    context["response"] = _run(
        context["agent"].process_message(
            tenant_id=context["tenant_id"],
            kb_id=context["kb_id"],
            user_message="保固政策說明",
        )
    )


@then("回答應包含知識庫內容")
def verify_rag_content(context):
    answer = context["response"].answer
    assert "知識庫" in answer or "退貨" in answer or "保固" in answer


@then("回答應附帶來源引用")
def verify_has_sources(context):
    assert len(context["response"].sources) > 0


@then("回答應使用 rag_query 工具")
def verify_rag_tool_used(context):
    assert context["response"].tool_calls[0]["tool_name"] == "rag_query"
