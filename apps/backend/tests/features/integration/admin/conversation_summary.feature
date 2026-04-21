Feature: 對話 LLM 摘要 + Hybrid 搜尋 — S-Gov.6b

  作為平台維運人員與管理員
  我希望系統自動為每個對話生成 LLM 摘要 + embedding
  以便管理員可用「關鍵字」或「意思」搜尋對話內容

  Background:
    Given admin 已登入
    And 已建立租戶 "summary-co"

  Scenario: 正常 cron 生 summary + 兩次 token tracking
    Given conversation "c1" 屬於 summary-co 含 5 messages，last_message_at 為 6 分鐘前
    When 執行 ProcessConversationSummaryUseCase 給 "c1"
    Then conversation "c1" 的 summary 應被寫入
    And conversation "c1" 的 summary_message_count 應為 5
    And usage_records 應有 1 筆 conversation_summary type
    And usage_records 應有 1 筆 embedding type
    And mock Milvus upsert_conv_summary 應被呼叫 1 次

  Scenario: Race-safe 重生 — 對話又動就重生 summary
    Given conversation "c2" 屬於 summary-co 含 5 messages，summary 已生 (summary_message_count=5)
    And conversation "c2" 寫入第 6 條 message
    When 執行 ProcessConversationSummaryUseCase 給 "c2"
    Then conversation "c2" 的 summary_message_count 應為 6
    And mock Milvus upsert_conv_summary 應被呼叫 1 次（覆蓋舊 vector）

  Scenario: Keyword 搜尋 — PG ILIKE on summary
    Given 已 seed 3 個 summary：
      | conv_name | summary_text          |
      | k1        | 客戶詢問退貨流程       |
      | k2        | 客戶想知道訂單狀態      |
      | k3        | 客戶要求加快退貨處理    |
    When admin 呼叫 GET /api/v1/admin/conversations/search?keyword=退貨
    Then 回應應包含 2 筆對話
    And 結果 conv_name 應包含 "k1" 與 "k3"

  Scenario: Semantic 搜尋 — Milvus vector + score
    Given 已 seed 2 個 summary 含對應 embedding：
      | conv_name | summary_text  |
      | s1        | 客戶在抱怨退貨   |
      | s2        | 客戶查詢訂單   |
    And mock Milvus search 設定 query="不滿" 命中 "s1" score=0.85
    When admin 呼叫 GET /api/v1/admin/conversations/search?semantic=不滿
    Then 回應應包含 1 筆對話
    And 該筆 conv_name 應為 "s1"
    And 該筆 score 應大於 0

  Scenario: POC quota 不計 — usage_records 寫入但 ledger 不被扣
    Given summary-co 的 included_categories 為 ["chat_web"]
    And conversation "p1" 屬於 summary-co 含 5 messages，last_message_at 為 6 分鐘前
    When 執行 ProcessConversationSummaryUseCase 給 "p1"
    Then usage_records 應有 1 筆 conversation_summary type
    And usage_records 應有 1 筆 embedding type
    And summary-co 本月 ledger 的 total_used_in_cycle 應為 0
