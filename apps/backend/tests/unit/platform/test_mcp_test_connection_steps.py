"""MCP Server Connection Test BDD Step Definitions"""

import asyncio
from unittest.mock import patch

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.platform.mcp.test_connection_use_case import (
    McpConnectionResult,
    TestMcpConnectionUseCase,
)

scenarios("unit/platform/mcp_test_connection.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


@given("一個可連線的 MCP Server")
def connectable_server(context):
    context["transport"] = "http"
    context["url"] = "http://localhost:3000/mcp"
    context["connectable"] = True


@given("一個無法連線的 MCP Server")
def unreachable_server(context):
    context["transport"] = "http"
    context["url"] = "http://unreachable:9999/mcp"
    context["connectable"] = False


@given("一個可連線的 stdio MCP Server")
def connectable_stdio_server(context):
    context["transport"] = "stdio"
    context["command"] = "python"
    context["args"] = ["-m", "server"]
    context["connectable"] = True


@when("我測試連線")
def execute_connection_test(context):
    use_case = TestMcpConnectionUseCase()

    if context.get("connectable"):
        async def _fake_test(**kwargs):
            return McpConnectionResult(success=True, tools_count=3)
    else:
        async def _fake_test(**kwargs):
            raise ConnectionError("Connection refused")

    with patch.object(
        TestMcpConnectionUseCase,
        "_do_test",
        side_effect=_fake_test,
    ):
        context["result"] = _run(
            use_case.execute(
                transport=context["transport"],
                url=context.get("url", ""),
                command=context.get("command", ""),
                args=context.get("args"),
            )
        )


@when("我測試 stdio 連線")
def execute_stdio_connection_test(context):
    use_case = TestMcpConnectionUseCase()

    async def _fake_test(**kwargs):
        return McpConnectionResult(success=True, tools_count=2)

    with patch.object(
        TestMcpConnectionUseCase,
        "_do_test",
        side_effect=_fake_test,
    ):
        context["result"] = _run(
            use_case.execute(
                transport="stdio",
                command=context.get("command", ""),
                args=context.get("args", []),
            )
        )


@then("應回傳成功且包含 tools_count")
def connection_success(context):
    result = context["result"]
    assert result.success is True
    assert result.tools_count > 0
    assert result.latency_ms >= 0


@then("應回傳失敗且包含錯誤訊息")
def connection_failure(context):
    result = context["result"]
    assert result.success is False
    assert result.error != ""


@then("應回傳 stdio 成功結果")
def stdio_success(context):
    result = context["result"]
    assert result.success is True
    assert result.tools_count > 0
