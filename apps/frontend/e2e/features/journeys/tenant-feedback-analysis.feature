Feature: 租戶管理員回饋分析與品質追蹤
  作為租戶管理員
  我希望能分析客服對話的回饋品質
  以持續改善 AI 客服表現

  Scenario: 從統計摘要到差評瀏覽的完整分析流程
    Given 租戶管理員已登入
    # Dashboard
    When 使用者進入回饋分析頁面
    Then 應顯示回饋統計摘要
    And 應顯示滿意度趨勢區塊
    And 應顯示 Token 成本統計區塊
    And 應顯示差評瀏覽器連結
    # Browser
    When 使用者進入差評瀏覽器頁面
    Then 應顯示差評瀏覽器標題
    And 應顯示回饋表格或空白狀態
