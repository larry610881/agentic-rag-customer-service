"""訂單查詢 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.agent.order_lookup_use_case import OrderLookupUseCase
from src.domain.agent.value_objects import ToolResult

scenarios("unit/agent/order_lookup.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


@given('訂單 "ord-001" 存在於資料庫中')
def order_exists(context):
    mock_service = AsyncMock()
    mock_service.lookup_order = AsyncMock(
        return_value=ToolResult(
            tool_name="order_lookup",
            success=True,
            data={
                "order_id": "ord-001",
                "order_status": "delivered",
                "estimated_delivery_date": "2024-01-20",
            },
        )
    )
    context["use_case"] = OrderLookupUseCase(order_lookup_service=mock_service)


@given('訂單 "ord-999" 不存在')
def order_not_exists(context):
    mock_service = AsyncMock()
    mock_service.lookup_order = AsyncMock(
        return_value=ToolResult(
            tool_name="order_lookup",
            success=False,
            error_message="Order 'ord-999' not found",
        )
    )
    context["use_case"] = OrderLookupUseCase(order_lookup_service=mock_service)


@given('訂單 "ord-001" 存在且包含商品資訊')
def order_with_product(context):
    mock_service = AsyncMock()
    mock_service.lookup_order = AsyncMock(
        return_value=ToolResult(
            tool_name="order_lookup",
            success=True,
            data={
                "order_id": "ord-001",
                "order_status": "delivered",
                "product_category": "electronics",
                "price": 99.90,
            },
        )
    )
    context["use_case"] = OrderLookupUseCase(order_lookup_service=mock_service)


@when('查詢訂單 "ord-001"')
def lookup_order_001(context):
    context["result"] = _run(context["use_case"].execute("ord-001"))


@when('查詢訂單 "ord-999"')
def lookup_order_999(context):
    context["result"] = _run(context["use_case"].execute("ord-999"))


@then("應回傳成功的 ToolResult")
def verify_success(context):
    assert context["result"].success is True


@then("應回傳失敗的 ToolResult")
def verify_failure(context):
    assert context["result"].success is False


@then('結果應包含訂單狀態 "delivered"')
def verify_status(context):
    assert context["result"].data["order_status"] == "delivered"


@then('錯誤訊息應包含 "not found"')
def verify_error_message(context):
    assert "not found" in context["result"].error_message


@then("結果應包含商品和價格資訊")
def verify_product_info(context):
    assert "product_category" in context["result"].data
    assert "price" in context["result"].data
