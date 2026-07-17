"""LINE 載入動畫 API 端點測試（POC 問題 1 UX — 動畫從未顯示的回歸修復）。

線上實證（2026-07-17 Cloud Run log）：`line.show_loading.failed` status 404
`{"message":"Not found"}` — 端點打成 `/v2/bot/chat/loading`，官方正確端點是
`/v2/bot/chat/loading/start`。fail-open 設計讓此錯誤靜默存在，動畫從未出現。
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

from src.infrastructure.line.line_messaging_service import (
    HttpxLineMessagingService,
)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_service() -> tuple[HttpxLineMessagingService, AsyncMock]:
    svc = HttpxLineMessagingService(
        channel_secret="secret", channel_access_token="token"
    )
    client = AsyncMock()
    resp = MagicMock()
    resp.status_code = 202
    resp.text = ""
    client.post = AsyncMock(return_value=resp)
    svc._client = client
    return svc, client


def test_show_loading_calls_official_start_endpoint():
    """必須打官方端點 /v2/bot/chat/loading/start（少 /start 會 404）。"""
    svc, client = _make_service()
    _run(svc.show_loading("U123", 20))
    url = client.post.await_args.args[0]
    assert url == "https://api.line.me/v2/bot/chat/loading/start"


def test_show_loading_payload_shape():
    """chatId 與 loadingSeconds（5 的倍數、上限 60）依官方格式送出。"""
    svc, client = _make_service()
    _run(svc.show_loading("U123", 20))
    payload = client.post.await_args.kwargs["json"]
    assert payload == {"chatId": "U123", "loadingSeconds": 20}
    assert payload["loadingSeconds"] % 5 == 0
