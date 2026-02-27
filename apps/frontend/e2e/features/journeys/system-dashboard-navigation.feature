Feature: 系統管理員儀表板全頁巡覽
  作為系統管理員
  我希望能巡覽所有功能頁面確認服務正常
  以便進行每日健康檢查

  Scenario: 依序巡覽所有儀表板頁面
    Given 使用者已登入為 "Demo Store"
    # Chat
    When 使用者在對話頁面
    Then 應顯示訊息輸入框
    # Knowledge
    When 使用者在知識庫頁面
    Then 應顯示知識庫列表
    # Bots
    When 使用者進入機器人管理頁面
    Then 應顯示機器人管理標題
    # Feedback
    When 使用者進入回饋分析頁面
    Then 應顯示回饋統計摘要
    # Provider Settings
    When 使用者進入供應商設定頁面
    Then 應顯示供應商設定標題
