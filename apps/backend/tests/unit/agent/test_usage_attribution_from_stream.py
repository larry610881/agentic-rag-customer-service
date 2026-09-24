"""串流記帳：cache token 不漏算、歸因欄位帶入（原整合測試 C3 / H8 的保護移到這一層）。

2c0bb53（M12）把串流記帳從 widget router 移進 SendMessageUseCase：router 不再建
TokenUsage、也不再呼叫 record_usage。原本在 tests/integration/bot/
test_widget_usage_recording.py 以 router 驗的兩件事改在 use case 驗（Issue #65）：
- C3：usage 事件轉 TokenUsage 時保留 cache token，total_tokens 含 cache
- H8：記帳帶 config_version_id / message_id，widget 通路 request_type 為 chat_widget
"""

import asyncio
from unittest.mock import AsyncMock

from src.application.agent.send_message_use_case import (
    SendMessageCommand,
    SendMessageUseCase,
)

USAGE_EVENT = {
    "type": "usage",
    "model": "claude-haiku-4-5",
    "input_tokens": 100,
    "output_tokens": 40,
    "estimated_cost": 0.0012,
    "cache_read_tokens": 120,
    "cache_creation_tokens": 40,
}


def test_usage_事件轉_TokenUsage_保留_cache_token():
    usage = SendMessageUseCase._usage_from_event(USAGE_EVENT)
    assert usage is not None
    assert (usage.cache_read_tokens, usage.cache_creation_tokens) == (120, 40)
    assert usage.total_tokens == 300  # input + output + cache_read + cache_creation


def test_widget_記帳帶歸因欄位與_chat_widget_分類():
    record = AsyncMock()
    uc = SendMessageUseCase.__new__(SendMessageUseCase)
    uc._record_usage = record  # 只測記帳這一段，不需要完整管線
    command = SendMessageCommand(
        tenant_id="t1",
        bot_id="b1",
        message="hi",
        usage_request_type="chat_widget",
    )
    asyncio.run(
        uc._record_turn_usage(
            command,
            SendMessageUseCase._usage_from_event(USAGE_EVENT),
            message_id="msg-7",
            config_version_id="ver-9",
            config_hash="h",
        )
    )
    kwargs = record.execute.await_args.kwargs
    assert kwargs["request_type"] == "chat_widget"
    assert kwargs["tenant_id"] == "t1"
    assert (kwargs["message_id"], kwargs["config_version_id"]) == ("msg-7", "ver-9")
    assert kwargs["usage"].cache_read_tokens == 120
