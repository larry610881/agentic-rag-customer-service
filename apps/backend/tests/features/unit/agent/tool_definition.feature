Feature: Tool Definition
  Agent 工具定義包含名稱描述和回應記錄

  Scenario: 建立工具定義包含名稱和描述
    Given 一個名為 "rag_query" 的工具定義
    Then 工具名稱應為 "rag_query"
    And 工具應包含描述和參數 schema

  Scenario: AgentResponse 包含工具調用記錄和來源
    Given 一個包含工具調用的 AgentResponse
    Then 回應應包含 answer
    And 回應應包含工具調用記錄
    And 回應應包含來源列表
