Feature: 系統管理員租戶隔離驗證
  作為系統管理員
  我希望驗證不同租戶的資料彼此隔離
  以確保平台安全性

  Scenario: 切換租戶後知識庫隔離且可復原
    Given 使用者已登入為 "Demo Store"
    And 使用者在知識庫頁面
    And 應包含知識庫 "商品資訊"
    And 應包含知識庫 "FAQ 常見問題"
    # Switch to Other Store
    When 使用者切換至租戶 "Other Store"
    And 使用者在知識庫頁面
    Then 不應顯示知識庫 "商品資訊"
    And 不應顯示知識庫 "FAQ 常見問題"
    And 不應顯示知識庫 "退換貨政策"
    # Switch back
    When 使用者切換至租戶 "Demo Store"
    And 使用者在知識庫頁面
    Then 應包含知識庫 "商品資訊"
