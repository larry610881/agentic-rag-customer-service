Feature: Agent Scenarios
  Agent 端對端場景能正確處理各類用戶請求（純 RAG 模式）

  Scenario: 用戶查詢退貨政策走 RAG 回答附帶來源
    Given Agent 服務已準備好處理知識查詢
    When 用戶查詢 "退貨政策是什麼"
    Then 回答應包含知識庫內容
    And 回答應附帶來源引用

  Scenario: 任意問題都透過 RAG 知識庫回答
    Given Agent 服務已準備好處理知識查詢
    When 用戶查詢 "保固政策說明"
    Then 回答應包含知識庫內容
    And 回答應使用 rag_query 工具
