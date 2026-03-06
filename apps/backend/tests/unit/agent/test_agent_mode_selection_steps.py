"""BDD steps for Agent Mode Selection."""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.agent.send_message_use_case import SendMessageUseCase
from src.domain.shared.exceptions import DomainException
from src.domain.tenant.entity import Tenant
from src.domain.tenant.value_objects import TenantId

scenarios("unit/agent/agent_mode_selection.feature")


def _run(coro):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


@pytest.fixture()
def context():
    return {}


@given(parsers.parse('一個 Bot 設定 agent_mode 為 "{mode}"'))
def setup_bot_agent_mode(context, mode):
    context["agent_mode"] = mode
    context["tenant_id"] = "tenant-1"
    context["router_service"] = AsyncMock()
    context["react_service"] = AsyncMock()
    context["react_available"] = True


@given(parsers.parse('Tenant 允許的 agent_modes 為 {modes_json}'))
def setup_tenant_modes(context, modes_json):
    modes = json.loads(modes_json)
    tenant = Tenant(
        id=TenantId(value=context["tenant_id"]),
        name="Test Tenant",
        allowed_agent_modes=modes,
    )
    tenant_repo = AsyncMock()
    tenant_repo.find_by_id.return_value = tenant
    context["tenant_repo"] = tenant_repo


@given("ReAct Agent Service 未註冊")
def react_not_registered(context):
    context["react_available"] = False


@when("發送訊息時解析 Agent Service")
def resolve_agent_service(context):
    react_svc = (
        context["react_service"]
        if context.get("react_available", True)
        else None
    )
    use_case = SendMessageUseCase(
        agent_service=context["router_service"],
        conversation_repository=AsyncMock(),
        react_agent_service=react_svc,
        tenant_repository=context["tenant_repo"],
    )
    try:
        result = _run(
            use_case._resolve_agent_service(
                context["tenant_id"], context["agent_mode"]
            )
        )
        context["resolved_service"] = result
        context["error"] = None
    except DomainException as e:
        context["resolved_service"] = None
        context["error"] = e


@then("應使用 Router Agent Service")
def check_router(context):
    assert context["error"] is None
    assert context["resolved_service"] is context["router_service"]


@then("應使用 ReAct Agent Service")
def check_react(context):
    assert context["error"] is None
    assert context["resolved_service"] is context["react_service"]


@then(parsers.parse('應拋出 DomainException 錯誤 "{msg}"'))
def check_error(context, msg):
    assert context["error"] is not None
    assert msg in str(context["error"])
