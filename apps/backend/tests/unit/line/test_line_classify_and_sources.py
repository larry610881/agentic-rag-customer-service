"""Regression: LINE 分類器歸屬（H9）與 dict 型 sources 回覆組裝（H10）。"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from src.application.line.handle_webhook_use_case import (
    HandleWebhookUseCase,
    WebhookContext,
    _format_line_source_lines,
)
from src.domain.agent.entity import AgentResponse
from src.domain.bot.entity import Bot
from src.domain.bot.value_objects import BotId, BotShortCode
from src.domain.line.entity import LineTextMessageEvent
from src.domain.rag.value_objects import Source


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# --- H10：dict 與 dataclass 混合 sources 不得崩潰 ---

def test_format_line_source_lines_handles_dict_and_dataclass():
    sources = [
        Source(document_name="退貨政策", content_snippet="s", score=0.9, chunk_id="c"),
        {"document_name": "DM 第 9 頁", "score": 0.4, "image_url": "u"},  # dict 快速道
        {"kb_id": "kb-1"},  # 無 document_name → 退回 kb_id
    ]
    lines = _format_line_source_lines(sources)
    assert lines == ["1. 退貨政策（90%）", "2. DM 第 9 頁（40%）", "3. kb-1（0%）"]


# --- H9：LINE 分類器呼叫帶 tenant_id / bot_id ---

def test_line_classify_passes_tenant_and_bot_id():
    bot = Bot(
        id=BotId(value="bot-line"),
        short_code=BotShortCode(value="sc"),
        tenant_id="tenant-line",
        name="Line Bot",
        knowledge_base_ids=["kb"],
    )
    worker_repo = AsyncMock()
    worker_repo.find_by_bot_id = AsyncMock(
        return_value=[type("W", (), {"name": "w1"})()]
    )
    classifier = AsyncMock()
    classifier.classify_sanitize = AsyncMock(
        return_value=type("O", (), {"worker": None, "query": "", "is_attack": False})()
    )
    agent = AsyncMock()
    agent.process_message = AsyncMock(return_value=AgentResponse(answer="ok"))
    line_service = AsyncMock()

    uc = HandleWebhookUseCase(
        agent_service=agent,
        bot_repository=AsyncMock(),
        line_service_factory=MagicMock(),
        worker_config_repo=worker_repo,
        intent_classifier=classifier,
    )
    ctx = WebhookContext(
        bot=bot,
        short_code="sc",
        line_service=line_service,
        events=[LineTextMessageEvent(
            reply_token="tk", user_id="U1", message_text="價格呢", timestamp=1,
        )],
    )
    _run(uc.process_and_push(ctx))

    classifier.classify_sanitize.assert_called_once()
    kwargs = classifier.classify_sanitize.call_args.kwargs
    assert kwargs["tenant_id"] == "tenant-line"
    assert kwargs["bot_id"] == "bot-line"
