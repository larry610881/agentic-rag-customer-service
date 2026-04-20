"""Token 用量分類 — 對應 UsageRecord.request_type 欄位值。

Token-Gov.0 將既有散落的 request_type 字串集中為 enum，
後續 ledger / 額度系統可依 category 過濾「該租戶哪些類型計費」。

不改 UsageRecord schema — request_type 仍是 String 欄位，向後相容。
"""

from enum import Enum


class UsageCategory(str, Enum):
    # 既有路徑（已接 RecordUsageUseCase）
    RAG = "rag"
    CHAT_WEB = "chat_web"
    CHAT_WIDGET = "chat_widget"
    CHAT_LINE = "chat_line"
    OCR = "ocr"
    EMBEDDING = "embedding"
    GUARD = "guard"
    # Token-Gov.0 新增（修漏網用）
    RERANK = "rerank"
    CONTEXTUAL_RETRIEVAL = "contextual_retrieval"
    PDF_RENAME = "pdf_rename"
    AUTO_CLASSIFICATION = "auto_classification"
    INTENT_CLASSIFY = "intent_classify"
    OTHER = "other"
