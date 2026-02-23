Feature: 租戶資料隔離 (Tenant Isolation)
  作為多租戶平台管理員
  我希望不同租戶的資料彼此隔離
  以便確保資料安全與隱私

  Background:
    Given 使用者已登入為 "Demo Store"

  Scenario: 切換租戶後看不到其他租戶的知識庫
    Given 使用者在知識庫頁面
    And 應包含知識庫 "商品資訊"
    When 使用者切換至租戶 "Other Store"
    And 使用者在知識庫頁面
    Then 不應顯示知識庫 "商品資訊"
    And 不應顯示知識庫 "FAQ 常見問題"
    And 不應顯示知識庫 "退換貨政策"
