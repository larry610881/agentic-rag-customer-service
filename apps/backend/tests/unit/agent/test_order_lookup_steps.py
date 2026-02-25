"""訂單查詢 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.agent.order_lookup_use_case import (
    OrderLookupCommand,
    OrderLookupUseCase,
)
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


# --- Existing Scenarios (by order_id) ---


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
            error_message="找不到訂單 'ord-999'",
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
    context["result"] = _run(
        context["use_case"].execute(OrderLookupCommand(order_id="ord-001"))
    )


@when('查詢訂單 "ord-999"')
def lookup_order_999(context):
    context["result"] = _run(
        context["use_case"].execute(OrderLookupCommand(order_id="ord-999"))
    )


# --- New Scenarios (by status / list all) ---


@given('資料庫中有 "shipped" 狀態的訂單')
def orders_with_shipped_status(context):
    mock_service = AsyncMock()
    mock_service.lookup_order = AsyncMock(
        return_value=ToolResult(
            tool_name="order_lookup",
            success=True,
            data={
                "orders": [
                    {"order_id": "ord-010", "order_status": "shipped", "price": 50.0},
                    {"order_id": "ord-011", "order_status": "shipped", "price": 75.0},
                ],
                "total": 2,
            },
        )
    )
    context["use_case"] = OrderLookupUseCase(order_lookup_service=mock_service)


@given("資料庫中有多筆訂單")
def orders_exist(context):
    mock_service = AsyncMock()
    mock_service.lookup_order = AsyncMock(
        return_value=ToolResult(
            tool_name="order_lookup",
            success=True,
            data={
                "orders": [
                    {"order_id": "ord-001", "order_status": "delivered"},
                    {"order_id": "ord-002", "order_status": "shipped"},
                    {"order_id": "ord-003", "order_status": "processing"},
                ],
                "total": 3,
            },
        )
    )
    context["use_case"] = OrderLookupUseCase(order_lookup_service=mock_service)


@given('沒有 "canceled" 狀態的訂單')
def no_canceled_orders(context):
    mock_service = AsyncMock()
    mock_service.lookup_order = AsyncMock(
        return_value=ToolResult(
            tool_name="order_lookup",
            success=False,
            error_message="沒有狀態為 'canceled' 的訂單",
        )
    )
    context["use_case"] = OrderLookupUseCase(order_lookup_service=mock_service)


@when('依狀態 "shipped" 查詢訂單')
def lookup_by_shipped(context):
    context["result"] = _run(
        context["use_case"].execute(OrderLookupCommand(status="shipped"))
    )


@when('依狀態 "canceled" 查詢訂單')
def lookup_by_canceled(context):
    context["result"] = _run(
        context["use_case"].execute(OrderLookupCommand(status="canceled"))
    )


@when("列出所有訂單")
def list_all_orders(context):
    context["result"] = _run(
        context["use_case"].execute(OrderLookupCommand())
    )


# --- Shared Then steps ---


@then("應回傳成功的 ToolResult")
def verify_success(context):
    assert context["result"].success is True


@then("應回傳失敗的 ToolResult")
def verify_failure(context):
    assert context["result"].success is False


@then('結果應包含訂單狀態 "delivered"')
def verify_status(context):
    assert context["result"].data["order_status"] == "delivered"


@then('錯誤訊息應包含 "ord-999"')
def verify_error_message(context):
    assert "ord-999" in context["result"].error_message


@then("結果應包含商品和價格資訊")
def verify_product_info(context):
    assert "product_category" in context["result"].data
    assert "price" in context["result"].data


@then("結果應包含訂單列表")
def verify_orders_list(context):
    assert "orders" in context["result"].data
    assert "total" in context["result"].data
    assert len(context["result"].data["orders"]) > 0


@then('所有訂單狀態應為 "shipped"')
def verify_all_shipped(context):
    for order in context["result"].data["orders"]:
        assert order["order_status"] == "shipped"
