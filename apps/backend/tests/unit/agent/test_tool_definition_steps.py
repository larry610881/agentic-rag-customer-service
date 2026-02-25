"""Agent 工具定義 BDD Step Definitions"""

import pytest
from pytest_bdd import given, scenarios, then

from src.domain.agent.entity import AgentResponse, ToolDefinition
from src.domain.rag.value_objects import Source

scenarios("unit/agent/tool_definition.feature")


@pytest.fixture
def context():
    return {}


@given('一個名為 "rag_query" 的工具定義')
def create_tool_definition(context):
    context["tool"] = ToolDefinition(
        name="rag_query",
        description="查詢知識庫回答用戶問題",
        parameters_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "用戶問題"},
            },
            "required": ["query"],
        },
    )


@given("一個包含工具調用的 AgentResponse")
def create_agent_response(context):
    context["response"] = AgentResponse(
        answer="退貨政策為 30 天內可退貨",
        tool_calls=[
            {"tool_name": "rag_query", "reasoning": "用戶詢問退貨政策"},
        ],
        sources=[
            Source(
                document_name="退貨政策.txt",
                content_snippet="退貨政策為 30 天內可退貨",
                score=0.95,
                chunk_id="chunk-1",
            ),
        ],
        conversation_id="conv-001",
    )


@then('工具名稱應為 "rag_query"')
def verify_tool_name(context):
    assert context["tool"].name == "rag_query"


@then("工具應包含描述和參數 schema")
def verify_tool_fields(context):
    assert context["tool"].description != ""
    assert "properties" in context["tool"].parameters_schema


@then("回應應包含 answer")
def verify_response_answer(context):
    assert context["response"].answer != ""


@then("回應應包含工具調用記錄")
def verify_response_tool_calls(context):
    assert len(context["response"].tool_calls) > 0
    assert "tool_name" in context["response"].tool_calls[0]


@then("回應應包含來源列表")
def verify_response_sources(context):
    assert len(context["response"].sources) > 0
    assert context["response"].sources[0].document_name != ""
