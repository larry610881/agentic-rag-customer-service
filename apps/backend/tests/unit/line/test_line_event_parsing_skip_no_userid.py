"""Regression: LINE 解析跳過無 userId 事件（M18）+ postback tenant fallback（L8）。"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

from src.application.line.handle_webhook_use_case import HandleWebhookUseCase
from src.domain.line.entity import LinePostbackEvent


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_parse_text_events_skips_group_event_without_userid():
    body = json.dumps({
        "events": [
            {  # 群組事件，source 無 userId → 原本 KeyError 毒殺整批
                "type": "message", "replyToken": "r1",
                "source": {"type": "group", "groupId": "g1"},
                "message": {"type": "text", "text": "hi group"},
                "timestamp": 1,
            },
            {  # 正常 1:1 事件
                "type": "message", "replyToken": "r2",
                "source": {"type": "user", "userId": "U1"},
                "message": {"type": "text", "text": "hi"},
                "timestamp": 2,
            },
        ]
    })
    events = HandleWebhookUseCase._parse_text_events(body)
    assert len(events) == 1  # 只留正常事件，不崩潰
    assert events[0].user_id == "U1"


def test_parse_postback_skips_no_userid():
    body = json.dumps({
        "events": [
            {"type": "postback", "replyToken": "r1",
             "source": {"type": "room", "roomId": "rm1"},
             "postback": {"data": "x"}, "timestamp": 1},
        ]
    })
    assert HandleWebhookUseCase._parse_postback_events(body) == []


def test_handle_postback_falls_back_to_default_tenant():
    feedback_repo = AsyncMock()
    uc = HandleWebhookUseCase(
        agent_service=AsyncMock(),
        bot_repository=AsyncMock(),
        line_service_factory=MagicMock(),
        default_tenant_id="tenant-default",
        feedback_repository=feedback_repo,
    )
    # feedback:{msg}:{rating} 格式觸發 submit
    ev = LinePostbackEvent(
        reply_token="r", user_id="U1",
        postback_data="feedback:msg-1:thumbs_up", timestamp=1,
    )
    feedback_repo.find_by_message_id = AsyncMock(return_value=None)
    _run(uc.handle_postback(ev, "", line_service=AsyncMock()))
    # 任一落到 feedback_repo 的呼叫都不應帶空 tenant_id
    for call in feedback_repo.method_calls:
        kwargs = call.kwargs
        if "tenant_id" in kwargs:
            assert kwargs["tenant_id"] == "tenant-default"
