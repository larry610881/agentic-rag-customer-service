# Token 用量記帳（token_usage_records）

> `token_usage_records` 是唯一的 quota truth（S-Ledger-Unification）。本文列出所有
> `UsageCategory`（`request_type` 欄位值）、每個類別的生產者，以及「每條花 token 的
> 路徑都必有一筆 usage」的覆蓋表。Issue #73（2026-09-07）補齊 embedding 缺口後更新。

## 記帳入口

- 唯一寫入口：`application/usage/record_usage_use_case.py::RecordUsageUseCase.execute`
  - `request_type` 必須是 `UsageCategory` 的值；deprecated 類別（`rag`、`guard`）
    只供讀取歷史紀錄，**新寫入一律拒絕**（`ValueError`）
  - `usage.total_tokens == 0` 直接略過（不寫空帳）
- 程式碼一律用 `UsageCategory.X.value`，禁止字串字面值；
  `tests/unit/usage/test_usage_accounting_coverage_steps.py` 有靜態守門
  （掃描 `src/` 的 `request_type="…"`，並檢查每個未淘汰類別都有生產者）。
- Embedding 記帳共用 helper：`application/usage/embedding_accounting.py::account_embedding`
  —— 用量來自 `EmbeddingResult`（供應商回傳），快取命中不入帳，fail-open。
- 文件管線（process / reprocess）共用 helper：`application/knowledge/_pipeline_accounting.py`。

## UsageCategory 一覽

| 值 | 說明 | 生產者（file） | bot_id | kb_id |
|---|---|---|---|---|
| `chat_web` | Web 對話（含 eval header fallback） | `application/usage/usage_context.py` → `agent_router` / `send_message_use_case` | ✅ | — |
| `chat_widget` | Widget 對話 | `interfaces/api/widget_router.py` | ✅ | — |
| `chat_line` | LINE 對話 | `application/line/handle_webhook_use_case.py` | ✅ | — |
| `playground` | 儲存前對照測試聊天 | `application/usage/usage_context.py` | ✅ | — |
| `eval_gate` | 閘門驗證的受測對話 | `application/prompt_gate/replay_use_cases.py` | ✅ | — |
| `prompt_optimize` | 優化迭代（受測對話 + mutator） | `application/eval_dataset/run_use_cases.py` | ✅ | — |
| `intent_classify` | worker 意圖分類 | `send_message_use_case` / `handle_webhook_use_case` | ✅ | — |
| `query_embedding` | **每輪檢索的查詢 embedding**（web / widget / LINE / search / Playground 單點） | `application/rag/query_rag_use_case.py`、`test_retrieval_use_case.py` | ✅（trace 上下文 fallback） | — |
| `rerank` | LLM rerank | `infrastructure/rag/llm_reranker.py` | ✅ | — |
| `query_rewrite` | 查詢改寫 | `application/rag/_query_rewriter.py` → `_aux_llm_accounting.py` | ✅ | — |
| `hyde` | HyDE 假答案 | `application/rag/_hyde_generator.py` → `_aux_llm_accounting.py` | ✅ | — |
| `history_summary` | summary_recent 歷史摘要 | `infrastructure/conversation/summary_recent_strategy.py` | ✅ | — |
| `memory_extraction` | 長期記憶萃取 | `application/memory/extract_memory_use_case.py` | ✅ | — |
| `ocr` | 文件 OCR（process / reprocess） | `application/knowledge/_pipeline_accounting.py` | — | ✅ |
| `contextual_retrieval` | Contextual retrieval（process / reprocess） | `application/knowledge/_pipeline_accounting.py` | — | ✅ |
| `embedding` | 文件 ingest / reprocess / reembed 的 embedding；對話摘要 embedding；管理端語意搜尋（SYSTEM tenant） | `_pipeline_accounting.py`、`reembed_chunk_use_case.py`、`generate_summary_use_case.py`、`search_conversations_use_case.py`、`admin_conv_summary_router.py` | 摘要 ✅ | ingest ✅ |
| `pdf_rename` | PDF 子頁 LLM 命名 | `application/knowledge/_child_rename.py` | — | ✅ |
| `auto_classification` | KB 自動分類命名 | `application/knowledge/classify_kb_use_case.py` | — | ✅ |
| `dm_metadata` | **DM 中繼資料抽取**（原借用 auto_classification） | `application/knowledge/extract_kb_dm_metadata_use_case.py` | — | ✅ |
| `conversation_summary` | 對話 LLM 摘要（cron） | `application/conversation/generate_summary_use_case.py` | ✅ | — |
| `rag` | **deprecated**（無生產者，只讀歷史） | — | | |
| `guard` | **deprecated**（無生產者，只讀歷史） | — | | |

## 覆蓋表：花了 token 就必有一筆 usage

| 路徑 | 類別 | 用量來源 | 狀態（#73 後） |
|---|---|---|---|
| 文件處理：OCR / contextual / embedding | `ocr` / `contextual_retrieval` / `embedding` | OCR、contextual：服務 `last_*` 累計屬性；embedding：`EmbeddingResult` | ✅ 三筆 |
| 文件重處理：OCR / contextual / embedding | 同上 | 同上（共用 `_pipeline_accounting`） | ✅ 三筆（之前 0 筆） |
| 每輪對話檢索（web / widget / LINE / 快速道 / LangGraph 工具） | `query_embedding` | `EmbeddingResult`；快取命中 0 筆 | ✅ 帶 bot_id |
| `/search`（unified search） | `query_embedding` | 同上 | ✅（無 bot） |
| Playground（含額外 conv_summaries embed） | `query_embedding` | 同上 | ✅ 帶 bot_id |
| 單 chunk reembed | `embedding` | `EmbeddingResult`（之前用字元數估） | ✅ |
| 對話摘要 embedding | `embedding` | `ConversationSummaryResult.embedding_tokens` ← `EmbeddingResult` | ✅（之前永遠 0） |
| 管理端對話語意搜尋（use case 與 router） | `embedding` | `EmbeddingResult` → SYSTEM tenant | ✅ |
| rerank / rewrite / HyDE / history_summary / memory_extraction | 各自類別 | LLM 回傳 usage | ✅ 帶 bot_id |
| DM 中繼資料抽取 | `dm_metadata` | extractor `last_*` | ✅ |
| RAGEvaluationUseCase | — | — | 已移除（無呼叫者；線上評估 09-03 下線） |

## bot_id 歸屬規則

`QueryRAGCommand.bot_id` 明確給 → 用之；否則退回 `AgentTraceCollector.current().bot_id`
（web / LINE 在 trace 啟動時已帶 bot）；仍為 None 則不歸屬（`/search`、管理端）。
`HistoryStrategyConfig.bot_id`、`ExtractMemoryCommand.bot_id` 由通路 / worker 傳入。

## 尚未處理

- `reasoning_tokens` 有算無存（#72）→ 併 #74 的 usage_records 改表。
- 前端 `usage-categories.ts` 的 label 需補 `query_embedding`、`dm_metadata`（本 Issue 不動前端）。
- OCR 引擎為 singleton，`last_*` 累計屬性在並行 reprocess 時可能互相污染（既有設計）。
