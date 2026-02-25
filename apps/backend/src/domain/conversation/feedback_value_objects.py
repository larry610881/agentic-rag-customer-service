"""Feedback 值物件"""

from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4


@dataclass(frozen=True)
class FeedbackId:
    value: str = field(default_factory=lambda: str(uuid4()))


class Rating(str, Enum):
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"


class Channel(str, Enum):
    WEB = "web"
    LINE = "line"
    API = "api"
