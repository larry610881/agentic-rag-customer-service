Feature: 回饋分析儀表板
  驗證回饋分析頁面的統計數據與趨勢圖表

  Background:
    Given 使用者已登入為 "Demo Store"

  Scenario: 瀏覽回饋分析主頁
    When 使用者進入回饋分析頁面
    Then 應顯示回饋統計摘要
    And 應顯示滿意度趨勢區塊
    And 應顯示 Token 成本統計區塊
    And 應顯示差評瀏覽器連結

  Scenario: 進入差評瀏覽器
    When 使用者進入差評瀏覽器頁面
    Then 應顯示差評瀏覽器標題
    And 應顯示回饋表格或空白狀態
