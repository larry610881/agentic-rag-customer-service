Feature: 知識庫詳情頁面
  驗證知識庫文件管理與品質指標

  Background:
    Given 使用者已登入為 "Demo Store"

  Scenario: 從列表進入知識庫詳情
    Given 使用者在知識庫頁面
    When 使用者點擊知識庫 "商品資訊"
    Then 應顯示文件管理頁面
    And 應顯示上傳區域
