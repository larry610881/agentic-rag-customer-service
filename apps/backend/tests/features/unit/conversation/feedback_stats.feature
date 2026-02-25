Feature: 回饋統計 (Feedback Statistics)

  Scenario: 查詢回饋統計
    Given 租戶 "tenant-1" 有 10 筆回饋，其中 7 筆正面 3 筆負面
    When 我查詢租戶 "tenant-1" 的回饋統計
    Then 總數應為 10
    And 滿意率應為 70.0

  Scenario: 無回饋時統計為零
    Given 租戶 "tenant-1" 沒有任何回饋
    When 我查詢租戶 "tenant-1" 的回饋統計
    Then 總數應為 0
    And 滿意率應為 0.0
