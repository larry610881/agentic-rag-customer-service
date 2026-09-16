"""對話回應的共用 schema（web chat / widget / 對話歷史共用）。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from pydantic.json_schema import JsonDict

_OPAQUE: JsonDict = {"x-opaque": True}


class ToolCallInfo(BaseModel):
    tool_name: str
    label: str = ""  # resolve 後的中文顯示名稱；空值時前端 fallback 為 tool_name
    reasoning: str


class SourceResponse(BaseModel):
    document_name: str
    content_snippet: str
    score: float


class StructuredContentResponse(BaseModel):
    """Issue #94：typed 結構化附件。`sources` 永遠是陣列（空時 `[]`）。"""

    contact: dict | None = Field(
        default=None,
        json_schema_extra=_OPAQUE,
        description="轉人工聯絡按鈕 {label, url, type: url|phone}；無則 null",
    )
    sources: list[dict] = Field(
        default_factory=list,
        description="檢索來源（含 chunk_id / document_id / kb_id / image_url）",
    )
    output: dict | None = Field(
        default=None,
        json_schema_extra=_OPAQUE,
        description="json bot 已解析的結構化答案（schema 由 bot 設定決定）",
    )


class HistoryStructuredContent(StructuredContentResponse):
    """對話歷史端點的 structured_content（持久化 payload 的 typed 形狀）。"""

    display_text: str | None = Field(
        default=None, description="文字通路顯示欄位（json bot 的 answer 欄）"
    )
    retrieval: dict[str, Any] | None = Field(
        default=None,
        json_schema_extra=_OPAQUE,
        description="快速道 / kb 檢索統計（top_score, chunk_count, threshold, miss）",
    )
