Feature: 分析查詢分頁 (Feedback Analysis Pagination)

  Scenario: 帶 offset 查詢回傳正確區間
    Given 租戶 "tenant-page" 有 25 筆差評資料
    When 查詢檢索品質分頁 offset 10 limit 10
    Then 應回傳 10 筆記錄與 total 25

  Scenario: offset 超出範圍回傳空列表
    Given 租戶 "tenant-page" 有 5 筆差評資料
    When 查詢檢索品質分頁 offset 100 limit 10
    Then 應回傳 0 筆記錄與 total 5
