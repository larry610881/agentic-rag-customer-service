"""LINE 限界上下文實體"""

from dataclasses import dataclass


@dataclass
class LineTextMessageEvent:
    reply_token: str
    user_id: str
    message_text: str
    timestamp: int
