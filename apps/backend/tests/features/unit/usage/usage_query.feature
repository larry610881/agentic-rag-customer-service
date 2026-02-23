Feature: Token 使用量查詢
  作為系統管理者
  我希望查詢租戶的 token 使用摘要
  以便監控各租戶的使用情況

  Scenario: 查詢租戶使用摘要
    Given 租戶 "tenant-001" 有 2 筆使用記錄
    When 查詢租戶 "tenant-001" 的使用摘要
    Then 摘要應包含正確的 total_tokens
    And 摘要應包含 by_model 分類

  Scenario: 按日期範圍查詢
    Given 租戶 "tenant-001" 有跨日期的使用記錄
    When 查詢指定日期範圍的使用摘要
    Then 只回傳範圍內的記錄摘要
