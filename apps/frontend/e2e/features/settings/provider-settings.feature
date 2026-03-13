Feature: 供應商設定頁面
  驗證 LLM 與 Embedding 供應商設定管理

  Background:
    Given 使用者已登入為 "Demo Store"

  Scenario: 瀏覽供應商設定頁面
    When 使用者進入供應商設定頁面
    Then 應顯示供應商設定標題
    And 應顯示供應商列表或空白狀態

  Scenario: 切換供應商類型篩選
    When 使用者進入供應商設定頁面
    Then 應顯示 LLM 與 API Key 分頁按鈕
