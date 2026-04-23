"""Regression (S-KB-Followup.1 Lv1): 對話聚合加 message preview + summary.

User report：觀測頁「對話聚合」只顯示 UUID prefix 認不出哪個對話。
Fix：list_traces_grouped_by_conversation 回傳加：
- first_user_message (截 200 字)
- last_assistant_answer (截 200 字)
- summary (from conversations.summary column)

本檔覆蓋 dataclass shape + _load_conversation_previews 的 helper 行為。
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.application.observability.agent_trace_queries import (
    ConversationTraceGroup,
    _truncate,
)


def test_ConversationTraceGroup_has_preview_fields():
    """dataclass 欄位齊全，避免未來 refactor 不小心拿掉 preview 欄位."""
    g = ConversationTraceGroup(
        conversation_id="conv-1",
        trace_count=2,
        first_at=datetime.now(timezone.utc),
        last_at=datetime.now(timezone.utc),
        traces=[],
        first_user_message="請問退貨？",
        last_assistant_answer="30 天內可退",
        summary="退貨諮詢",
    )
    assert g.first_user_message == "請問退貨？"
    assert g.last_assistant_answer == "30 天內可退"
    assert g.summary == "退貨諮詢"


def test_ConversationTraceGroup_preview_fields_optional():
    """沒 summary / preview 的舊對話也能建（向下相容）."""
    g = ConversationTraceGroup(
        conversation_id="conv-1",
        trace_count=1,
        first_at=datetime.now(timezone.utc),
        last_at=datetime.now(timezone.utc),
        traces=[],
    )
    assert g.first_user_message is None
    assert g.last_assistant_answer is None
    assert g.summary is None


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, None),
        ("", ""),
        ("短", "短"),
        ("a" * 200, "a" * 200),  # 剛好 200
        ("a" * 201, "a" * 200),  # 超過 200 → 截
        ("請問退貨流程是什麼？", "請問退貨流程是什麼？"),
    ],
)
def test_truncate_respects_200_char_limit(value, expected):
    assert _truncate(value) == expected
