Feature: 共用分頁
  所有列表 API 支援 page/page_size 分頁

  Scenario: 第一頁查詢
    Given 有 25 筆機器人資料
    When 查詢第 1 頁每頁 10 筆
    Then 應回傳 10 筆資料
    And total 為 25
    And total_pages 為 3

  Scenario: 最後一頁查詢
    Given 有 25 筆機器人資料
    When 查詢第 3 頁每頁 10 筆
    Then 應回傳 5 筆資料

  Scenario: 超出頁數回傳空列表
    Given 有 5 筆機器人資料
    When 查詢第 10 頁每頁 10 筆
    Then 應回傳 0 筆資料
    And total 為 5
