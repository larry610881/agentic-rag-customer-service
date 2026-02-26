Feature: 對話摘要 Redis 快取 (Summary Cache)

  Scenario: 相同對話摘要只呼叫 LLM 一次
    Given 一段包含 10 則訊息的對話歷史且摘要快取 TTL 為 300 秒
    When 連續兩次執行 summary_recent 策略
    Then LLM generate 應只被呼叫一次

  Scenario: 摘要快取帶有 TTL
    Given 一段包含 10 則訊息的對話歷史且摘要快取 TTL 為 300 秒
    When 執行 summary_recent 策略一次
    Then 快取中應存在對應的摘要 key 且有 TTL
