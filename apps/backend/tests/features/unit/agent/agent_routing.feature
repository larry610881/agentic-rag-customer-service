Feature: Agent Routing
  Agent 能根據用戶意圖路由到正確的工具

  Scenario: 知識型問題路由到 RAGTool
    Given Agent 服務已初始化
    When 用戶發送訊息 "退貨政策是什麼"
    Then Agent 應選擇 "rag_query" 工具

  Scenario: Agent 回應包含工具選擇理由
    Given Agent 服務已初始化
    When 用戶發送訊息 "退貨政策是什麼"
    Then 回應應包含工具調用記錄
    And 工具調用記錄應包含選擇理由
