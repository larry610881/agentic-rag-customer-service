Feature: Bot Model Selection
  機器人可以指定使用的 LLM 供應商與模型

  Scenario: 建立機器人時指定 LLM 供應商與模型
    Given 一個新機器人的建立請求包含 llm_provider "openai" 和 llm_model "gpt-5-mini"
    When 我執行建立機器人用例
    Then 機器人的 llm_provider 應為 "openai"
    And 機器人的 llm_model 應為 "gpt-5-mini"

  Scenario: 更新機器人的 LLM 模型
    Given 已存在一個機器人使用 "openai" 的 "gpt-5"
    When 我更新機器人的模型為 "anthropic" 的 "claude-sonnet-4-6"
    Then 機器人的 llm_provider 應為 "anthropic"
    And 機器人的 llm_model 應為 "claude-sonnet-4-6"
