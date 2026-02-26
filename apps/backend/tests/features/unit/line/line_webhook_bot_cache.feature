Feature: Bot 查詢 TTL 快取 (Bot Query Cache)

  Scenario: 同 Bot ID 連續請求只查一次 DB
    Given Bot "bot-cache-001" 已設定且快取 TTL 為 60 秒
    When 系統連續兩次處理同一 Bot ID 的 Webhook
    Then Bot Repository 應只查詢一次

  Scenario: TTL 過期後重新查 DB
    Given Bot "bot-cache-002" 已設定且快取 TTL 為 0 秒
    When 系統連續兩次處理同一 Bot ID 的 Webhook
    Then Bot Repository 應查詢兩次
