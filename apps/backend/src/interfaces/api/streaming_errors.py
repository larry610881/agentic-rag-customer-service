"""Streaming error mapping — shared by agent_router and widget_router."""

import httpx


def classify_streaming_error(exc: Exception) -> str:
    """Map an exception to a user-friendly error message.

    - httpx.HTTPStatusError 429 → rate limit message
    - httpx.HTTPStatusError 5xx → LLM service error
    - Everything else → generic safe message (no traceback leak)
    """
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 429:
            return "API 額度已用完，請稍後再試"
        if 500 <= status < 600:
            return "LLM 服務異常"
    return "處理訊息時發生錯誤，請重試"
