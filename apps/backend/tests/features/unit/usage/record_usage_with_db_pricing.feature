Feature: RecordUsageUseCase 串接 DB Pricing
  作為 RecordUsageUseCase
  我希望優先查 PricingCache，cache miss 時 fallback 到 DEFAULT_MODELS
  以便新上架 pricing 即時生效，同時避免 DB 空導致 estimated_cost=0

  Scenario: cache 命中時使用 DB 價格計算 cost
    Given PricingCache 已載入 "anthropic" "claude-haiku-4-5" input=1.20 output=6.00
    And DEFAULT_MODELS 有 "anthropic" "claude-haiku-4-5" input=1.0 output=5.0
    When RecordUsageUseCase 收到一筆 TokenUsage model="anthropic:claude-haiku-4-5" estimated_cost=0 input_tokens=1000 output_tokens=500
    Then 儲存的 UsageRecord.estimated_cost 應以 DB 價格計算 input=1.20 output=6.00
    And UsageRecord.estimated_cost 不應為 0

  Scenario: cache miss 時 fallback 到 DEFAULT_MODELS
    Given PricingCache 對 "anthropic:claude-haiku-4-5" 回傳 None
    And DEFAULT_MODELS 有 "anthropic" "claude-haiku-4-5" input=1.0 output=5.0
    When RecordUsageUseCase 收到一筆 TokenUsage model="anthropic:claude-haiku-4-5" estimated_cost=0 input_tokens=1000 output_tokens=500
    Then 儲存的 UsageRecord.estimated_cost 應以 DEFAULT_MODELS 價格計算
    And UsageRecord.estimated_cost 不應為 0

  Scenario: TokenUsage 已帶 estimated_cost 則不重算
    Given PricingCache 已載入 "anthropic" "claude-haiku-4-5"
    When RecordUsageUseCase 收到一筆 TokenUsage model="anthropic:claude-haiku-4-5" estimated_cost=99.99
    Then 儲存的 UsageRecord.estimated_cost 應為 99.99
    And PricingCache.lookup 不應被呼叫
