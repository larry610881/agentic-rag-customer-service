Feature: Agent Reflection
  Agent 自我反思檢查回答品質

  Scenario: 回答足夠長度通過反思
    Given 反思機制已啟用的 Agent
    When Agent 產生足夠長度的回答
    Then 回答不應被修改

  Scenario: 過短回答觸發反思補充
    Given 反思機制已啟用的 Agent
    When Agent 產生過短的回答
    Then 回答應被補充延伸
