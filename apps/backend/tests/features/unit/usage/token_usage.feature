Feature: Token Usage 追蹤
  作為系統管理者
  我希望每次 LLM 呼叫都記錄 token 使用量
  以便追蹤成本與使用模式

  # Scenario: RAG 查詢結果包含 token 使用量（已刪 — S-KB-Followup.2 清 pure RAG legacy）
  # 原測試 QueryRAGUseCase.execute() 的 RAGResponse.usage，但 .execute() 已移除
  # (/rag/query endpoint 與對應 use case method 隨 pure RAG 模式 deprecation 一起刪)。
  # ReAct 主對話的 token 記錄由 agent_router 的 stream usage_data 流程保證（a5407a8 stream_usage=True fix）。

  Scenario: FakeLLM 回傳零 usage
    Given 使用 FakeLLMService
    When 呼叫 generate 生成回答
    Then 回傳的 LLMResult 應包含 TokenUsage
    And usage 的 total_tokens 應為 0

  Scenario: RecordUsageUseCase 自動補算 estimated_cost
    Given 一筆 TokenUsage 的 estimated_cost 為 0 但有 tokens
    When 執行 RecordUsageUseCase
    Then 儲存的 UsageRecord 的 estimated_cost 應大於 0

  Scenario: RecordUsageUseCase 不覆蓋已有的 estimated_cost
    Given 一筆 TokenUsage 已包含正確的 estimated_cost
    When 執行 RecordUsageUseCase
    Then 儲存的 UsageRecord 的 estimated_cost 應等於原始值

  Scenario: TokenUsage 支援累加
    Given 兩個 TokenUsage 物件
    When 將兩個 usage 相加
    Then 結果的 input_tokens 應為兩者之和
    And 結果的 output_tokens 應為兩者之和
    And 結果的 estimated_cost 應為兩者之和

  Scenario: extract_usage_from_accumulated 保留 cache tokens
    Given 一個包含 cache tokens 的 accumulated usage dict
    When 用 extract_usage_from_accumulated 轉換
    Then 結果應包含 cache_read_tokens 和 cache_creation_tokens

  Scenario: extract_usage_from_langchain_messages 正規化 OpenAI cache tokens
    Given 一組 OpenAI 風格的 AIMessage 其 input_tokens 包含 cached
    When 用 extract_usage_from_langchain_messages 提取
    Then input_tokens 應已扣除 cached 避免重複計算
    And cache_read_tokens 應等於 cached 數量

  Scenario: extract_usage_from_langchain_messages 保留 Anthropic cache tokens
    Given 一組 Anthropic 風格的 AIMessage 其 input_tokens 不含 cache
    When 用 extract_usage_from_langchain_messages 提取
    Then input_tokens 應維持原始值不扣除
    And cache_read_tokens 應等於 cache_read 數量
    And cache_creation_tokens 應等於 cache_creation 數量

  Scenario: RecordUsageUseCase fallback 成本計算含 cache tokens
    Given 一筆含 cache tokens 但 estimated_cost 為 0 的 TokenUsage
    When 執行 RecordUsageUseCase
    Then 儲存的成本應高於只算 input+output 的成本
