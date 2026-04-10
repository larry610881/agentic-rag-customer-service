Feature: Bot Wiki 知識模式設定
  作為系統管理員，我要能在 Bot 設定頁切換 Wiki 模式、觸發編譯、看到狀態變化

  Background:
    Given 使用者已登入為 "Demo Store"
    And Wiki 編譯與狀態端點已被 mock

  Scenario: Wiki 模式顯示編譯區塊與導航策略
    When 使用者進入機器人管理頁面
    And 使用者點擊第一個機器人卡片
    And 使用者切換知識模式為 "wiki"
    Then 應顯示 Wiki 編譯卡片
    And 應顯示導航策略 "Keyword + BFS（推薦）"

  Scenario: 觸發 Wiki 編譯顯示確認對話框並送出
    When 使用者進入機器人管理頁面
    And 使用者點擊第一個機器人卡片
    And 使用者切換知識模式為 "wiki"
    And 使用者點擊「編譯 Wiki」按鈕
    Then 應顯示確認編譯對話框
    When 使用者確認編譯
    Then Wiki 編譯端點應被呼叫

  Scenario: Wiki 編譯狀態為 ready 時顯示統計資訊
    When 使用者進入機器人管理頁面
    And 使用者點擊第一個機器人卡片
    And 使用者切換知識模式為 "wiki"
    Then Wiki 狀態 badge 應顯示 "已就緒"
    And 應顯示節點統計與 Token 用量
