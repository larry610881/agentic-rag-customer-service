Feature: ReAct Agent 執行流程
  作為系統，我需要驗證 ReAct Agent 能正確執行 RAG 和 MCP 工具呼叫

  Scenario: RAG tool 回答知識型問題
    Given 一個 ReAct Agent 配置了 RAG 工具
    And RAG 工具查詢後回傳 "退貨政策：30天內可退貨"
    When 用戶詢問 "退貨政策是什麼？"
    Then Agent 應呼叫 rag_query 工具
    And 最終回答應包含工具結果

  Scenario: MCP tool 回答外部查詢
    Given 一個 ReAct Agent 配置了 MCP 工具 "query_products"
    And MCP 工具 "query_products" 回傳 "商品A: $100"
    When 用戶詢問 "有什麼商品？"
    Then Agent 應呼叫 query_products 工具
    And 最終回答應包含工具結果

  Scenario: 混合 RAG 和 MCP tool
    Given 一個 ReAct Agent 配置了 RAG 和 MCP 工具
    And RAG 工具查詢後回傳 "退貨政策：30天內可退貨"
    And MCP 工具 "query_products" 回傳 "商品A: $100"
    When 用戶詢問 "退貨政策和商品資訊"
    Then Agent 應呼叫至少 1 個工具
    And 最終回答應包含工具結果

  Scenario: max_tool_calls 達上限停止
    Given 一個 ReAct Agent 配置了 RAG 工具
    And max_tool_calls 設為 2
    When 用戶詢問需要多次查詢的問題
    Then Agent 的工具呼叫次數不應超過 2 次

  Scenario: MCP 連線失敗 graceful degradation
    Given 一個 ReAct Agent 配置了 MCP 工具但連線失敗
    And RAG 工具查詢後回傳 "退貨政策：30天內可退貨"
    When 用戶詢問 "退貨政策是什麼？"
    Then Agent 應正常運作只使用 RAG 工具
    And 最終回答應包含工具結果
