Feature: List Enabled Models
  只回傳已啟用供應商中已啟用的模型

  Scenario: 只回傳已啟用供應商的已啟用模型
    Given 有一個啟用的 "openai" LLM 供應商包含 3 個模型且其中 1 個已停用
    And 有一個停用的 "anthropic" LLM 供應商
    When 我查詢已啟用的模型列表
    Then 應回傳 2 個模型
    And 所有模型都來自 "openai"

  Scenario: 無啟用供應商時回傳空列表
    Given 沒有任何啟用的 LLM 供應商
    When 我查詢已啟用的模型列表
    Then 應回傳空列表
