Feature: Agent Routing
  Agent 能根據用戶意圖路由到正確的工具

  Scenario: 訂單查詢問題路由到 OrderLookupTool
    Given Agent 服務已初始化
    When 用戶發送訊息 "我的訂單 ORD-001 到哪了"
    Then Agent 應選擇 "order_lookup" 工具

  Scenario: 商品搜尋問題路由到 ProductSearchTool
    Given Agent 服務已初始化
    When 用戶發送訊息 "有什麼電子產品"
    Then Agent 應選擇 "product_search" 工具

  Scenario: 知識型問題路由到 RAGTool
    Given Agent 服務已初始化
    When 用戶發送訊息 "退貨政策是什麼"
    Then Agent 應選擇 "rag_query" 工具

  Scenario: 投訴問題路由到 TicketCreationTool
    Given Agent 服務已初始化
    When 用戶發送訊息 "我要投訴"
    Then Agent 應選擇 "ticket_creation" 工具

  Scenario: Agent 回應包含工具選擇理由
    Given Agent 服務已初始化
    When 用戶發送訊息 "我的訂單 ORD-001 到哪了"
    Then 回應應包含工具調用記錄
    And 工具調用記錄應包含選擇理由
