"""Regression：LINE 追問原因的標籤更新要綁定租戶（Issue #102）。

postback「feedback_reason:{msg_id}:{tag}」原本呼叫 update_tags(message_id, [tag])
不帶 tenant_id，repository 因此不加租戶條件，可把標籤寫到他租戶同 message_id 的回饋上。
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from src.application.line.handle_webhook_use_case import HandleWebhookUseCase
from src.domain.line.entity import LinePostbackEvent


def test_追問原因的標籤更新帶上租戶():
    feedback_repo = AsyncMock()
    uc = HandleWebhookUseCase(
        agent_service=MagicMock(),
        bot_repository=AsyncMock(),
        line_service_factory=MagicMock(),
        feedback_repository=feedback_repo,
    )
    event = LinePostbackEvent(
        reply_token="r",
        user_id="U1",
        postback_data="feedback_reason:msg-1:不準確",
        timestamp=0,
    )

    asyncio.run(uc.handle_postback(event, tenant_id="tenant-a"))

    feedback_repo.update_tags.assert_awaited_once_with(
        "msg-1", ["不準確"], tenant_id="tenant-a"
    )
