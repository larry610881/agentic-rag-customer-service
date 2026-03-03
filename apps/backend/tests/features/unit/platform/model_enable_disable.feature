Feature: Model Enable/Disable
  供應商的個別模型可以被啟用或停用

  Scenario: 建立供應商設定時自動填充預設模型
    Given 供應商 "openai" 的 "llm" 類型尚未建立設定
    When 我建立供應商設定且不指定模型列表
    Then 應自動從預設模型註冊表填充模型
    And 所有模型預設為啟用狀態

  Scenario: 建立供應商設定時保留指定的模型列表
    Given 供應商 "openai" 的 "llm" 類型尚未建立設定
    When 我建立供應商設定並指定模型列表
    Then 應使用我指定的模型列表

  Scenario: 更新供應商設定時停用個別模型
    Given 已有啟用中的 "openai" LLM 供應商設定
    When 我更新模型列表將 "gpt-5-mini" 設為停用
    Then "gpt-5-mini" 的 is_enabled 應為 False
    And 其他模型的 is_enabled 應維持 True
