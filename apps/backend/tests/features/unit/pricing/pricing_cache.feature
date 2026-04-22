Feature: PricingCache 記憶體快取與 fallback
  作為 RecordUsageUseCase
  我希望在 hot path 不打 DB
  並在 cache miss 時 fallback 到 DEFAULT_MODELS 避免 estimated_cost=0

  Scenario: 啟動時從 DB load 所有生效 pricing
    Given DB 有 3 筆生效中的 pricing: openai/gpt-5, anthropic/claude-haiku-4-5, litellm/azure_ai/claude-sonnet-4-5
    When PricingCache 啟動載入
    Then cache 應包含 3 組 (provider, model_id) 的索引

  Scenario: lookup 命中 DB 快取
    Given PricingCache 已載入 "anthropic" "claude-haiku-4-5" input=1.0 output=5.0
    When 查詢 "anthropic:claude-haiku-4-5" at=now
    Then 應回傳 dict 含 input=1.0 output=5.0

  Scenario: lookup miss 時回傳 None
    Given PricingCache 為空
    When 查詢 "openai:gpt-unknown-model" at=now
    Then 應回傳 None

  Scenario: lookup 自動剝除 provider 前綴
    Given PricingCache 已載入 "litellm" "azure_ai/claude-haiku-4-5" input=1.0 output=5.0
    When 查詢 "litellm:azure_ai/claude-haiku-4-5" at=now
    Then 應回傳 dict 含 input=1.0 output=5.0

  Scenario: 查詢歷史時點回傳當時生效版本
    Given PricingCache 有 "openai" "gpt-5" 兩個版本: v1 effective_from=T0, v2 effective_from=T1
    When 查詢 "openai:gpt-5" at=T0+1sec
    Then 應回傳 v1 的價格
    When 查詢 "openai:gpt-5" at=T1+1sec
    Then 應回傳 v2 的價格

  Scenario: refresh 重新載入 DB 變更
    Given PricingCache 已載入 "openai" "gpt-5" input=1.25
    When 管理員建立新版本 input=1.30 effective_from=now+1sec 且呼叫 cache.refresh()
    Then 查詢 "openai:gpt-5" at=now+2sec 應回傳 input=1.30
