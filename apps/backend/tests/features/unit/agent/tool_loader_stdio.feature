Feature: MCP Tool Loader stdio Transport
  CachedMCPToolLoader 支援 stdio transport

  Scenario: 載入 stdio MCP Server 工具
    Given 一個 stdio 類型的 MCP Server 配置
    When 我透過 CachedMCPToolLoader 載入工具
    Then 應成功載入 stdio 工具

  Scenario: 向後相容 URL 字串
    Given 一個 legacy URL 字串 "http://localhost:3000/mcp"
    When 我透過 CachedMCPToolLoader 載入工具
    Then 應以 HTTP transport 載入工具
