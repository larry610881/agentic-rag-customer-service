"""Token 用量分類 — 對應 UsageRecord.request_type 欄位值。

Token-Gov.0 將既有散落的 request_type 字串集中為 enum，
後續 ledger / 額度系統可依 category 過濾「該租戶哪些類型計費」。

不改 UsageRecord schema — request_type 仍是 String 欄位，向後相容。
"""

from enum import Enum


class UsageCategory(str, Enum):
    # 既有路徑（已接 RecordUsageUseCase）
    # Issue #73：`rag` / `guard` 已無生產者 → deprecated。保留成員是為了讀取
    # 歷史 usage_records（查詢 / 報表相容），RecordUsageUseCase 拒絕新寫入。
    RAG = "rag"
    CHAT_WEB = "chat_web"
    CHAT_WIDGET = "chat_widget"
    CHAT_LINE = "chat_line"
    OCR = "ocr"
    EMBEDDING = "embedding"            # 文件 ingest / reembed / 摘要與管理端 embedding
    GUARD = "guard"
    # Token-Gov.0 新增（修漏網用）
    RERANK = "rerank"
    CONTEXTUAL_RETRIEVAL = "contextual_retrieval"
    PDF_RENAME = "pdf_rename"
    AUTO_CLASSIFICATION = "auto_classification"
    INTENT_CLASSIFY = "intent_classify"
    # S-Gov.6b: 對話 LLM 摘要（cron 行為，POC 預設不計入 quota）
    CONVERSATION_SUMMARY = "conversation_summary"
    # Issue #54 Phase B — Eval token 分流（定案 2/14：三分類獨立記帳，租戶自付）
    EVAL_GATE = "eval_gate"                # 閘門驗證的受測對話
    PROMPT_OPTIMIZE = "prompt_optimize"    # 優化迭代（受測對話 + mutator LLM）
    PLAYGROUND = "playground"              # 儲存前對照測試聊天
    # Issue #59 — 原本沒記帳的輔助 LLM 呼叫（開啟這些功能的 bot 成本曾被低估）
    QUERY_REWRITE = "query_rewrite"
    HYDE = "hyde"
    MEMORY_EXTRACTION = "memory_extraction"
    HISTORY_SUMMARY = "history_summary"    # summary_recent 歷史策略的摘要呼叫
    # Issue #73 — 記帳缺口
    QUERY_EMBEDDING = "query_embedding"    # 每輪檢索的查詢 embedding（帶 bot_id）
    DM_METADATA = "dm_metadata"            # DM 中繼資料抽取（原借 auto_classification）
    # OTHER 已刪 — src/ 零 caller 是 dead code；UI 不再提供「其他」checkbox。
    # RecordUsageUseCase 入口會白名單拒絕非此 enum 的字串。


# 已淘汰、只供讀取歷史紀錄的類別；RecordUsageUseCase 拒絕以這些值新寫入。
DEPRECATED_CATEGORIES: frozenset[str] = frozenset(
    {UsageCategory.RAG.value, UsageCategory.GUARD.value}
)
