"""客服工單建立 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.agent.ticket_creation_use_case import TicketCreationUseCase
from src.domain.agent.value_objects import ToolResult

scenarios("unit/agent/ticket_creation.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


@given('租戶 "tenant-001" 需要建立工單')
def tenant_needs_ticket(context):
    mock_service = AsyncMock()
    mock_service.create_ticket = AsyncMock(
        return_value=ToolResult(
            tool_name="ticket_creation",
            success=True,
            data={
                "ticket_id": "ticket-001",
                "tenant_id": "tenant-001",
                "subject": "商品瑕疵",
                "order_id": "",
                "status": "open",
            },
        )
    )
    context["use_case"] = TicketCreationUseCase(ticket_service=mock_service)
    context["tenant_id"] = "tenant-001"
    context["order_id"] = ""


@given('租戶 "tenant-001" 需要建立與訂單 "ord-001" 相關的工單')
def tenant_needs_ticket_with_order(context):
    mock_service = AsyncMock()
    mock_service.create_ticket = AsyncMock(
        return_value=ToolResult(
            tool_name="ticket_creation",
            success=True,
            data={
                "ticket_id": "ticket-002",
                "tenant_id": "tenant-001",
                "subject": "訂單問題",
                "order_id": "ord-001",
                "status": "open",
            },
        )
    )
    context["use_case"] = TicketCreationUseCase(ticket_service=mock_service)
    context["tenant_id"] = "tenant-001"
    context["order_id"] = "ord-001"


@when('建立工單主題為 "商品瑕疵" 描述為 "收到的商品有損壞"')
def create_ticket_defect(context):
    context["result"] = _run(
        context["use_case"].execute(
            tenant_id=context["tenant_id"],
            subject="商品瑕疵",
            description="收到的商品有損壞",
            order_id=context["order_id"],
        )
    )


@when('建立工單主題為 "訂單問題" 描述為 "訂單遲遲未到"')
def create_ticket_order(context):
    context["result"] = _run(
        context["use_case"].execute(
            tenant_id=context["tenant_id"],
            subject="訂單問題",
            description="訂單遲遲未到",
            order_id=context["order_id"],
        )
    )


@then("應回傳成功的工單建立結果")
def verify_success(context):
    assert context["result"].success is True


@then("結果應包含工單 ID")
def verify_ticket_id(context):
    assert "ticket_id" in context["result"].data
    assert context["result"].data["ticket_id"] != ""


@then('結果應包含 tenant_id "tenant-001"')
def verify_tenant_id(context):
    assert context["result"].data["tenant_id"] == "tenant-001"


@then('結果應包含 order_id "ord-001"')
def verify_order_id(context):
    assert context["result"].data["order_id"] == "ord-001"
