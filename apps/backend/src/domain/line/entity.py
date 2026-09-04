"""LINE 限界上下文實體"""

from dataclasses import dataclass


@dataclass
class LineTextMessageEvent:
    reply_token: str
    user_id: str
    message_text: str
    timestamp: int
    # Issue #58：LINE 每個事件唯一 ID，redelivery 重送時相同 → 去重 key。
    # 舊 payload / 測試可能沒有 → 空字串表示不去重。
    webhook_event_id: str = ""
    is_redelivery: bool = False
    # Issue #68 P7b：群組 / 聊天室 id（1:1 為 None）
    group_id: str | None = None


@dataclass
class LinePostbackEvent:
    reply_token: str
    user_id: str
    postback_data: str
    timestamp: int
    webhook_event_id: str = ""
    is_redelivery: bool = False
