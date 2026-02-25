Feature: Provider Setting Management
  管理 LLM / Embedding 供應商設定

  Scenario: 成功建立 LLM 供應商設定
    Given 系統中尚未有 "llm" 類型的 "openai" 供應商
    When 我建立一個 "llm" 類型的 "openai" 供應商設定，顯示名稱為 "OpenAI"
    Then 供應商設定應成功建立
    And 供應商類型應為 "llm"
    And 供應商名稱應為 "openai"
    And 供應商應為啟用狀態

  Scenario: 建立重複供應商應失敗
    Given 系統中已有 "llm" 類型的 "openai" 供應商
    When 我建立一個 "llm" 類型的 "openai" 供應商設定，顯示名稱為 "OpenAI"
    Then 應拋出重複實體錯誤

  Scenario: 停用供應商設定
    Given 一個已啟用的供應商設定
    When 我停用該供應商設定
    Then 供應商應為停用狀態
