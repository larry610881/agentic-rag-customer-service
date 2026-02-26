Feature: CacheService 快取基礎操作 (Cache Service Base Operations)

  Scenario: set 後 get 取得相同值
    Given 一個空的快取服務
    When 設定 key "foo" 值為 "bar" 且 TTL 為 300 秒
    Then 查詢 key "foo" 應回傳 "bar"

  Scenario: TTL 過期後 get 回傳 None
    Given 一個空的快取服務
    When 設定 key "expire-me" 值為 "data" 且 TTL 已過期
    Then 查詢 key "expire-me" 應回傳 None

  Scenario: delete 後 get 回傳 None
    Given 一個已有 key "to-delete" 值為 "hello" 的快取
    When 刪除 key "to-delete"
    Then 查詢 key "to-delete" 應回傳 None

  Scenario: Redis 斷線時 get 靜默回傳 None
    Given 一個 Redis 連線異常的快取服務
    When 查詢 key "any-key"
    Then 應回傳 None 而非拋出例外
