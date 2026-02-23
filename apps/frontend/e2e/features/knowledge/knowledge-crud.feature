Feature: 知識庫管理 (Knowledge Base Management)
  作為電商平台管理員
  我希望能夠管理知識庫
  以便維護 AI 客服所需的知識內容

  Background:
    Given 使用者已登入為 "demo@example.com"

  Scenario: 登入後瀏覽知識庫列表
    Given 使用者在知識庫頁面
    Then 應顯示知識庫列表
    And 應包含知識庫 "商品資訊"
    And 應包含知識庫 "FAQ"
    And 應包含知識庫 "退換貨政策"

  Scenario: 查看知識庫詳情與文件列表
    Given 使用者在知識庫頁面
    When 使用者點擊知識庫 "商品資訊"
    Then 應顯示知識庫名稱 "商品資訊"
    And 應顯示文件列表
    And 每個文件應顯示名稱與狀態
