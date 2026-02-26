Feature: 回饋統計 TTL 快取 (Feedback Stats Cache)

  Scenario: 連續查詢統計只查一次 DB
    Given 租戶 "tenant-stats-1" 有回饋資料且快取 TTL 為 60 秒
    When 連續兩次查詢回饋統計
    Then Repository 的 count 方法應只被呼叫一輪

  Scenario: TTL 過期後重新查 DB
    Given 租戶 "tenant-stats-2" 有回饋資料且快取 TTL 為 0 秒
    When 連續兩次查詢回饋統計
    Then Repository 的 count 方法應被呼叫兩輪
