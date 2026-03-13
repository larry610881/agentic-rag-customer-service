Feature: 系統管理員平台環境建置
  作為系統管理員
  我希望能設定供應商、建立知識庫、管理機器人
  以完成平台初始化

  Scenario: 從供應商設定到 Bot 建立的完整環境初始化
    Given 使用者已登入為 "Demo Store"
    # Step 1: Provider Settings
    When 使用者進入供應商設定頁面
    Then 應顯示供應商設定標題
    And 應顯示 LLM 與 API Key 分頁按鈕
    # Step 2: Knowledge Base
    When 使用者在知識庫頁面
    Then 應顯示知識庫列表
    And 應包含知識庫 "商品資訊"
    # Step 3: KB Detail
    When 使用者點擊知識庫 "商品資訊"
    Then 應顯示文件管理頁面
    And 應顯示上傳區域
    # Step 4: Bot Management
    When 使用者進入機器人管理頁面
    Then 應顯示機器人管理標題
    And 應顯示機器人列表或空白狀態
