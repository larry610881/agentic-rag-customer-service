"""對外契約共用型別（Issue #97）。

ApiDateTime：所有回應的 datetime 只輸出一種形狀——UTC、`Z` 結尾、固定三位小數
（微秒為 0 也輸出 `.000`）。Pydantic 預設在微秒為 0 時省略小數、否則六位，
同一欄位兩種形狀會讓 Swift `.iso8601` 這類嚴格 decoder 間歇性失敗（準則 A2）。
只用在回應模型；請求端維持 `datetime`（接受 0–9 位小數）。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from pydantic import PlainSerializer, WithJsonSchema

API_DATETIME_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$"


def serialize_api_datetime(value: datetime) -> str:
    """UTC、Z、固定三位小數。naive 視為 UTC（專案 DB 欄位皆 timezone=True，保險用）。"""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    value = value.astimezone(timezone.utc)
    return f"{value.strftime('%Y-%m-%dT%H:%M:%S')}.{value.microsecond // 1000:03d}Z"


ApiDateTime = Annotated[
    datetime,
    PlainSerializer(serialize_api_datetime, return_type=str, when_used="json"),
    WithJsonSchema(
        {"type": "string", "format": "date-time", "pattern": API_DATETIME_PATTERN},
        mode="serialization",
    ),
]
