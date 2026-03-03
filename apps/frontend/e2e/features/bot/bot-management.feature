Feature: Bot 管理頁面
  驗證機器人管理頁面的基本功能

  Background:
    Given 使用者已登入為 "Demo Store"

  Scenario: 瀏覽機器人列表頁面
    When 使用者進入機器人管理頁面
    Then 應顯示機器人管理標題
    And 應顯示機器人列表或空白狀態

  Scenario: 機器人卡片顯示基本資訊
    When 使用者進入機器人管理頁面
    Then 每個機器人應顯示名稱與狀態標籤
