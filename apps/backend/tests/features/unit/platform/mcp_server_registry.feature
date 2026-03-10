Feature: MCP Server Registry CRUD
  管理員可建立、查詢、更新、刪除 MCP Server 註冊

  Scenario: 建立 HTTP 類型 MCP Server
    Given 一個空的 MCP Server 註冊庫
    When 我建立一個 HTTP 類型的 MCP Server "test-server" 使用 URL "http://localhost:3000/mcp"
    Then 應成功建立且 transport 為 "http"

  Scenario: 建立 stdio 類型 MCP Server
    Given 一個空的 MCP Server 註冊庫
    When 我建立一個 stdio 類型的 MCP Server "local-tool" 使用 command "python"
    Then 應成功建立且 transport 為 "stdio"

  Scenario: HTTP 類型需要 URL
    Given 一個空的 MCP Server 註冊庫
    When 我建立一個 HTTP 類型的 MCP Server 但不提供 URL
    Then 應拋出錯誤 "HTTP transport requires a URL"

  Scenario: stdio 類型需要 command
    Given 一個空的 MCP Server 註冊庫
    When 我建立一個 stdio 類型的 MCP Server 但不提供 command
    Then 應拋出錯誤 "stdio transport requires a command"

  Scenario: 不允許重複的 HTTP URL
    Given 一個已有 URL "http://example.com/mcp" 的 MCP Server 註冊庫
    When 我建立一個 HTTP 類型的 MCP Server 使用相同 URL "http://example.com/mcp"
    Then 應拋出重複錯誤

  Scenario: 更新 MCP Server
    Given 一個已有名為 "old-name" 的 MCP Server
    When 我更新該 Server 名稱為 "new-name"
    Then 更新後的 Server 名稱應為 "new-name"

  Scenario: 刪除 MCP Server
    Given 一個已有名為 "to-delete" 的 MCP Server
    When 我刪除該 Server
    Then 刪除方法應被呼叫
