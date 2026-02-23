"""Domain Events BDD Step Definitions"""

import asyncio

import pytest
from pytest_bdd import given, scenarios, then, when

from src.domain.shared.events import (
    NegativeSentimentDetected,
    OrderRefunded,
)
from src.infrastructure.events.in_memory_event_bus import InMemoryEventBus

scenarios("unit/agent/domain_events.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


@given("建立一個 OrderRefunded 事件")
def create_order_refunded(context):
    context["event"] = OrderRefunded(
        tenant_id="tenant-001",
        order_id="ORD-123",
        amount=1500.0,
        reason="商品損壞",
    )


@given("EventBus 已訂閱 OrderRefunded 事件的處理器")
def subscribe_single_handler(context):
    context["bus"] = InMemoryEventBus()
    context["calls"] = []

    async def handler(event):
        context["calls"].append(event)

    _run(context["bus"].subscribe(OrderRefunded, handler))


@given("EventBus 已訂閱兩個 OrderRefunded 事件的處理器")
def subscribe_two_handlers(context):
    context["bus"] = InMemoryEventBus()
    context["calls_a"] = []
    context["calls_b"] = []

    async def handler_a(event):
        context["calls_a"].append(event)

    async def handler_b(event):
        context["calls_b"].append(event)

    _run(context["bus"].subscribe(OrderRefunded, handler_a))
    _run(context["bus"].subscribe(OrderRefunded, handler_b))


@given("EventBus 已訂閱 OrderRefunded 和 NegativeSentimentDetected 處理器")
def subscribe_different_types(context):
    context["bus"] = InMemoryEventBus()
    context["refund_calls"] = []
    context["sentiment_calls"] = []

    async def refund_handler(event):
        context["refund_calls"].append(event)

    async def sentiment_handler(event):
        context["sentiment_calls"].append(event)

    _run(context["bus"].subscribe(OrderRefunded, refund_handler))
    _run(
        context["bus"].subscribe(
            NegativeSentimentDetected, sentiment_handler
        )
    )


@when("發佈一個 OrderRefunded 事件")
def publish_order_refunded(context):
    event = OrderRefunded(
        tenant_id="tenant-001",
        order_id="ORD-456",
        amount=2000.0,
        reason="不想要了",
    )
    context["published_event"] = event
    _run(context["bus"].publish(event))


@then("事件應有非空的 event_id")
def verify_event_id(context):
    assert context["event"].event_id != ""
    assert len(context["event"].event_id) > 0


@then("事件應有 occurred_at 時戳")
def verify_occurred_at(context):
    assert context["event"].occurred_at is not None


@then("tenant_id 應為指定值")
def verify_tenant_id(context):
    assert context["event"].tenant_id == "tenant-001"


@then("訂閱的處理器應被呼叫一次")
def verify_handler_called_once(context):
    assert len(context["calls"]) == 1


@then("處理器收到的事件應包含正確的 order_id")
def verify_event_order_id(context):
    assert context["calls"][0].order_id == "ORD-456"


@then("兩個處理器都應被呼叫")
def verify_both_handlers_called(context):
    assert len(context["calls_a"]) == 1
    assert len(context["calls_b"]) == 1


@then("OrderRefunded 處理器應被呼叫")
def verify_refund_handler_called(context):
    assert len(context["refund_calls"]) == 1


@then("NegativeSentimentDetected 處理器不應被呼叫")
def verify_sentiment_handler_not_called(context):
    assert len(context["sentiment_calls"]) == 0
