Feature: Token 追蹤完整性 — Token-Gov.0 五條漏網路徑修復後驗證

  作為平台維運人員
  我希望所有 LLM 路徑的 token 用量都被記錄到 token_usage_records
  以便後續 ledger / 計費 / 額度系統能算對

  Scenario: Contextual Retrieval LLM 跑完 — last token 屬性已填，category=contextual_retrieval
    Given LLMChunkContextService 配置好 mock call_llm 回傳 input=100 output=50
    And 文件內容 "退貨政策說明" 與 1 個 chunk
    When 呼叫 generate_contexts
    Then last_input_tokens 應為 100
    And last_output_tokens 應為 50
    And last_model 不應為空

  Scenario: LLM Reranker 跑完 — record_usage 被呼叫 且 category=rerank 含 cache 欄位
    Given llm_rerank 配置好 mock anthropic 回傳 input=200 output=80 cache_read=30
    And 注入 mock RecordUsageUseCase + tenant_id="tenant-001"
    When 呼叫 llm_rerank 重排 6 個 chunks 取 top 3
    Then RecordUsageUseCase.execute 應被呼叫 1 次
    And 該 call 的 request_type 應為 "rerank"
    And 該 call 的 cache_read_tokens 應為 30

  Scenario: ClassifyKbUseCase 跑完 — record_usage 被呼叫 且 category=auto_classification
    Given ClassifyKbUseCase 配置好 mock cluster service 已累計 input=500 output=200
    And 注入 mock RecordUsageUseCase
    When 呼叫 ClassifyKbUseCase.execute kb_id="kb-1" tenant_id="tenant-1"
    Then RecordUsageUseCase.execute 應被呼叫 1 次
    And 該 call 的 request_type 應為 "auto_classification"
    And 該 call 的 input_tokens 應為 500

  Scenario: IntentClassifier classify_workers 跑完 — record_usage 被呼叫 且 category=intent_classify
    Given IntentClassifier 配置好 mock LLMService 回傳 input=80 output=20
    And 注入 mock RecordUsageUseCase + tenant_id="tenant-2"
    When 呼叫 classify_workers 帶 1 個 worker
    Then RecordUsageUseCase.execute 應被呼叫 1 次
    And 該 call 的 request_type 應為 "intent_classify"
    And 該 call 的 tenant_id 應為 "tenant-2"

  Scenario: UsageCategory enum 涵蓋所有需要的分類
    Given UsageCategory enum 已定義
    When 列出所有 enum 值
    Then 應至少包含 "rag" "embedding" "rerank" "contextual_retrieval" "pdf_rename" "auto_classification" "intent_classify"
