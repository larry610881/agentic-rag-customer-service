"""LINE 前置斷點儀表測試（Issue #49 — PM 要求逐斷點計時）

之前 AgentTraceCollector 在 process_message 內才啟動，webhook 前置
（歷史載入 / 輸入守門 / 意圖分類）約 1.4s 在 trace 中整塊不可見。
此測試鎖定：trace 自 webhook t0 起算，前置各段以獨立節點記錄。
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from src.application.line.handle_webhook_use_case import HandleWebhookUseCase
from src.domain.agent.entity import AgentResponse
from src.domain.bot.entity import Bot
from src.infrastructure.observability.agent_trace_collector import (
    AgentTraceCollector,
)

BODY = (
    '{"events":[{"type":"message","replyToken":"token-bp-001",'
    '"source":{"userId":"U-bp-user"},'
    '"message":{"type":"text","text":"請問營業時間"},'
    '"timestamp":1700000000000}]}'
)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_webhook_records_front_breakpoint_nodes(monkeypatch):
    """trace 應含 history_load 與 input_guard 前置節點。"""
    bot = Bot(
        tenant_id="tenant-bp",
        name="Breakpoint Bot",
        line_channel_secret="secret-bp",
        line_channel_access_token="token-bp",
        knowledge_base_ids=["kb-bp"],
    )
    mock_bot_repo = AsyncMock()
    mock_bot_repo.find_by_short_code = AsyncMock(return_value=bot)
    mock_line_service = AsyncMock()
    mock_line_service.verify_signature = AsyncMock(return_value=True)
    mock_factory = MagicMock()
    mock_factory.create = MagicMock(return_value=mock_line_service)
    mock_agent = AsyncMock()
    mock_agent.process_message = AsyncMock(
        return_value=AgentResponse(answer="OK")
    )
    mock_guard = AsyncMock()
    mock_guard.check_input = AsyncMock(
        return_value=MagicMock(passed=True, rule_matched=None)
    )

    recorded: list[str] = []
    original_add_node = AgentTraceCollector.add_node

    def spy_add_node(node_type, label, parent_id, start_ms, end_ms, **kw):
        recorded.append(node_type)
        return original_add_node(
            node_type, label, parent_id, start_ms, end_ms, **kw
        )

    monkeypatch.setattr(AgentTraceCollector, "add_node", staticmethod(spy_add_node))

    use_case = HandleWebhookUseCase(
        agent_service=mock_agent,
        bot_repository=mock_bot_repo,
        line_service_factory=mock_factory,
        prompt_guard=mock_guard,
    )
    _run(use_case.execute_for_bot("BP01", BODY, "sig"))

    assert "history_load" in recorded, f"缺 history_load 節點: {recorded}"
    assert "input_guard" in recorded, f"缺 input_guard 節點: {recorded}"
    # 回覆流程不受影響
    mock_line_service.reply_with_quick_reply.assert_called_once()
