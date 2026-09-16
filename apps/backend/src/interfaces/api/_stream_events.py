"""SSE 事件的通路共用轉接（channel parity）：web / widget 都用同一份。"""

from __future__ import annotations


def conversation_created(requested_id: str | None, actual_id: str) -> bool:
    """Issue #94：平台回傳的 id 與請求端帶的不同（含未帶）= 新建對話。"""
    return requested_id is None or requested_id != actual_id


def with_conversation_created(event: dict, requested_id: str | None) -> dict:
    """`conversation_id` 事件補 `conversation_created`，與非串流回應對等。"""
    if event.get("type") != "conversation_id":
        return event
    return {
        **event,
        "conversation_created": conversation_created(
            requested_id, str(event.get("conversation_id", ""))
        ),
    }
