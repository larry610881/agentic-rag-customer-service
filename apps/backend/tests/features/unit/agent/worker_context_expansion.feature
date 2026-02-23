Feature: WorkerContext 擴展
  WorkerContext 新增 user_role、user_permissions、mcp_tools 欄位，
  支援多角色 Agent 路由與 MCP 工具發現。

  Scenario: WorkerContext 預設角色為 customer
    Given 建立一個未指定角色的 WorkerContext
    Then user_role 應為 "customer"
    And user_permissions 應為空列表
    And mcp_tools 應為空字典

  Scenario: WorkerContext 可設定 marketing 角色與權限
    Given 建立一個 marketing 角色的 WorkerContext
    And 權限包含 "campaign:create" 和 "campaign:read"
    Then user_role 應為 "marketing"
    And user_permissions 應包含 "campaign:create"
    And user_permissions 應包含 "campaign:read"

  Scenario: WorkerContext 可攜帶 MCP 工具資訊
    Given 建立一個帶有 MCP 工具的 WorkerContext
    And MCP 工具包含 "knowledge_search" 和 "order_lookup"
    Then mcp_tools 應包含 "knowledge_search" 鍵
    And mcp_tools 應包含 "order_lookup" 鍵
