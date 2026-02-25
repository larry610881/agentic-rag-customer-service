"""退貨多步驟引導 BDD Step Definitions"""

import asyncio

import pytest
from pytest_bdd import given, scenarios, then, when

from src.domain.agent.worker import WorkerContext
from src.infrastructure.langgraph.workers.fake_refund_worker import (
    FakeRefundWorker,
    _RefundStep,
)

scenarios("unit/agent/refund_workflow.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


@given("Agent 退貨服務已初始化")
def refund_service_initialized(context):
    context["worker"] = FakeRefundWorker()


@given("退貨流程在收集原因步驟")
def refund_at_collect_reason(context):
    context["metadata"] = {"refund_step": _RefundStep.collect_reason.value}


@given("退貨流程在確認步驟")
def refund_at_confirm(context):
    context["metadata"] = {"refund_step": _RefundStep.confirm.value}


@when('用戶發送 "我想退貨"')
def send_refund_request(context):
    worker_ctx = WorkerContext(
        tenant_id="tenant-001",
        kb_id="kb-001",
        user_message="我想退貨",
        metadata=context.get("metadata", {}),
    )
    context["can_handle"] = _run(context["worker"].can_handle(worker_ctx))
    context["result"] = _run(context["worker"].handle(worker_ctx))


@when('用戶發送 "ORD-001"')
def send_order_id(context):
    worker_ctx = WorkerContext(
        tenant_id="tenant-001",
        kb_id="kb-001",
        user_message="ORD-001",
        metadata=context.get("metadata", {}),
    )
    context["result"] = _run(context["worker"].handle(worker_ctx))


@when('用戶發送 "商品有瑕疵"')
def send_reason(context):
    worker_ctx = WorkerContext(
        tenant_id="tenant-001",
        kb_id="kb-001",
        user_message="商品有瑕疵",
        metadata=context.get("metadata", {}),
    )
    context["result"] = _run(context["worker"].handle(worker_ctx))


@then("回應應要求提供訂單編號")
def verify_ask_order_id(context):
    assert "訂單編號" in context["result"].answer


@then("回應應詢問退貨原因")
def verify_ask_reason(context):
    assert "退貨原因" in context["result"].answer


@then("回應應包含退貨工單編號")
def verify_ticket_created(context):
    assert "TK-" in context["result"].answer
