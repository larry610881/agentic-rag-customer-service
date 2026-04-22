Feature: Cache-Aware Token 計費
  作為系統管理者
  我希望 LLM 成本計算能正確反映快取優惠
  以便帳單金額與 API 供應商實際收費一致

  Scenario: OpenAI 快取命中時成本應低於全價
    Given 模型 "gpt-5.1" 的定價為 input 1.25 cache_read 0.125 output 10.0 per 1M tokens
    When 計算 800 non-cached input、200 cache_read、0 cache_creation、500 output tokens 的成本
    Then estimated_cost 應低於無快取的全價計算
    And cache_read_tokens 應為 200

  Scenario: Anthropic 三段式計費正確計算
    Given 模型 "claude-sonnet-4-6" 的定價為 input 3.0 cache_read 0.3 cache_creation 3.75 output 15.0 per 1M tokens
    When 計算 100 non-cached input、500 cache_read、200 cache_creation、300 output tokens 的成本
    Then estimated_cost 應為各段費用之和
    And cache_read_tokens 應為 500
    And cache_creation_tokens 應為 200

  Scenario: 無快取時與舊邏輯一致
    Given 模型 "gpt-5.1" 的定價為 input 1.25 cache_read 0.125 output 10.0 per 1M tokens
    When 計算 1000 non-cached input、0 cache_read、0 cache_creation、500 output tokens 的成本
    Then estimated_cost 應為 0.00625

  Scenario: TokenUsage 累加包含快取 tokens
    Given 兩個含快取 tokens 的 TokenUsage 物件
    When 將兩個 usage 相加
    Then 結果的 cache_read_tokens 應為兩者之和
    And 結果的 cache_creation_tokens 應為兩者之和

  Scenario: RecordUsageUseCase 正確儲存快取 tokens
    Given 一筆包含快取 tokens 的 TokenUsage
    When 執行 RecordUsageUseCase
    Then 儲存的 UsageRecord 應包含 cache_read_tokens 和 cache_creation_tokens

  Scenario: Contextual Retrieval 多 chunk 回傳 cache 命中（S-LLM-Cache.1）
    Given LLMChunkContextService 處理同一文件的 5 個 chunks
    And 第一個 chunk 的 LLM 回應 cache_creation_tokens=1000、cache_read_tokens=0
    And 後續 4 個 chunks 的 LLM 回應每筆 cache_read_tokens=1000、cache_creation_tokens=0
    When 完成 generate_contexts
    Then service 累計 last_cache_creation_tokens 應為 1000
    And service 累計 last_cache_read_tokens 應為 4000
