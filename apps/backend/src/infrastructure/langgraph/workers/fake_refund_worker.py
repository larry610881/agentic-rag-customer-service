"""FakeRefundWorker — 退貨多步驟引導 Worker"""

import re
from enum import Enum
from uuid import uuid4

from src.domain.agent.worker import AgentWorker, WorkerContext, WorkerResult
from src.domain.rag.value_objects import TokenUsage

_REFUND_KEYWORDS = re.compile(r"退貨|退款|refund|退回|退換")
_ORDER_ID_PATTERN = re.compile(r"ORD-\w+", re.IGNORECASE)


class _RefundStep(str, Enum):
    """Refund workflow steps (local to this fake worker)."""
    collect_order = "collect_order"
    collect_reason = "collect_reason"
    confirm = "confirm"


class FakeRefundWorker(AgentWorker):
    """退貨流程 Worker：3 步驟引導（收集訂單號 → 收集原因 → 建立工單）"""

    @property
    def name(self) -> str:
        return "fake_refund"

    async def can_handle(self, context: WorkerContext) -> bool:
        if context.metadata.get("refund_step"):
            return True
        return bool(_REFUND_KEYWORDS.search(context.user_message))

    async def handle(self, context: WorkerContext) -> WorkerResult:
        step = self._determine_step(context)

        if step == _RefundStep.collect_order:
            return WorkerResult(
                answer="好的，我來協助您處理退貨。請提供您的訂單編號（例如 ORD-001）。",
                tool_calls=[
                    {
                        "tool_name": "refund_workflow",
                        "reasoning": "開始退貨流程，收集訂單號",
                    }
                ],
                usage=TokenUsage.zero("fake"),
                metadata={"refund_step": _RefundStep.collect_reason.value},
            )

        if step == _RefundStep.collect_reason:
            order_id = self._extract_order_id(context)
            return WorkerResult(
                answer=f"已找到訂單 {order_id}。請問您的退貨原因是什麼？",
                tool_calls=[
                    {
                        "tool_name": "refund_workflow",
                        "reasoning": "已收集訂單號，收集退貨原因",
                    }
                ],
                usage=TokenUsage.zero("fake"),
                metadata={"refund_step": _RefundStep.confirm.value},
            )

        ticket_id = f"TK-{uuid4().hex[:6].upper()}"
        return WorkerResult(
            answer=f"已為您建立退貨工單 {ticket_id}，我們會盡快處理。",
            tool_calls=[
                {
                    "tool_name": "refund_workflow",
                    "reasoning": "退貨流程完成，建立工單",
                }
            ],
            usage=TokenUsage.zero("fake"),
            metadata={"refund_step": None},
        )

    def _determine_step(self, context: WorkerContext) -> _RefundStep:
        current_step = context.metadata.get("refund_step")

        if current_step == _RefundStep.confirm.value:
            return _RefundStep.confirm

        if current_step == _RefundStep.collect_reason.value:
            if _ORDER_ID_PATTERN.search(context.user_message):
                return _RefundStep.collect_reason
            return _RefundStep.collect_reason

        if self._has_order_in_history(context):
            return _RefundStep.collect_reason

        return _RefundStep.collect_order

    def _extract_order_id(self, context: WorkerContext) -> str:
        match = _ORDER_ID_PATTERN.search(context.user_message)
        if match:
            return match.group()
        for msg in reversed(context.conversation_history):
            match = _ORDER_ID_PATTERN.search(msg.content)
            if match:
                return match.group()
        return "ORD-UNKNOWN"

    def _has_order_in_history(self, context: WorkerContext) -> bool:
        for msg in context.conversation_history:
            if _ORDER_ID_PATTERN.search(msg.content):
                return True
        return False
