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
from src.domain.rag.value_objects import Source, TokenUsage


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


def test_line_classify_router_model_falls_back_to_tenant_default():
    """M19：bot.router_model 空 → 退回租戶 default_intent_model（與 web 一致）。"""
    bot = Bot(
        id=BotId(value="bot-line"),
        short_code=BotShortCode(value="sc"),
        tenant_id="tenant-line",
        name="Line Bot",
        knowledge_base_ids=["kb"],
        router_model="",  # 空 → 走 tenant fallback
    )
    worker_repo = AsyncMock()
    worker_repo.find_by_bot_id = AsyncMock(
        return_value=[type("W", (), {"name": "w1"})()]
    )
    classifier = AsyncMock()
    classifier.classify_sanitize = AsyncMock(
        return_value=type(
            "O", (), {"worker": None, "query": "", "is_attack": False}
        )()
    )
    tenant_repo = AsyncMock()
    tenant_repo.find_by_id = AsyncMock(
        return_value=type("T", (), {"default_intent_model": "openai:gpt-4o-mini"})()
    )
    agent = AsyncMock()
    agent.process_message = AsyncMock(return_value=AgentResponse(answer="ok"))

    uc = HandleWebhookUseCase(
        agent_service=agent,
        bot_repository=AsyncMock(),
        line_service_factory=MagicMock(),
        worker_config_repo=worker_repo,
        intent_classifier=classifier,
        tenant_repository=tenant_repo,
    )
    ctx = WebhookContext(
        bot=bot, short_code="sc", line_service=AsyncMock(),
        events=[LineTextMessageEvent(
            reply_token="tk", user_id="U1", message_text="hi", timestamp=1,
        )],
    )
    _run(uc.process_and_push(ctx))

    kwargs = classifier.classify_sanitize.call_args.kwargs
    assert kwargs["router_model"] == "openai:gpt-4o-mini"


def test_line_record_usage_uses_real_assistant_message_id():
    """H8：LINE record_usage 的 message_id 應為 assistant_msg.id（非 result.message_id
    ——後者對 LINE 恆 None，會讓版本成效 join 不到 LINE 訊息）。"""
    bot = Bot(
        id=BotId(value="bot-line"),
        short_code=BotShortCode(value="sc"),
        tenant_id="tenant-line",
        name="Line Bot",
        knowledge_base_ids=["kb"],
    )
    agent = AsyncMock()
    agent.process_message = AsyncMock(return_value=AgentResponse(
        answer="ok",
        usage=TokenUsage(model="m", input_tokens=10, output_tokens=5),
        message_id=None,  # AgentResponse 對 LINE 不帶 message_id
    ))
    record_spy = AsyncMock()
    record_spy.execute = AsyncMock(return_value=None)

    uc = HandleWebhookUseCase(
        agent_service=agent,
        bot_repository=AsyncMock(),
        line_service_factory=MagicMock(),
        record_usage_use_case=record_spy,
    )
    ctx = WebhookContext(
        bot=bot,
        short_code="sc",
        line_service=AsyncMock(),
        events=[LineTextMessageEvent(
            reply_token="tk", user_id="U1", message_text="hi", timestamp=1,
        )],
    )
    _run(uc.process_and_push(ctx))

    record_spy.execute.assert_called_once()
    mid = record_spy.execute.call_args.kwargs["message_id"]
    assert mid is not None and mid != ""
