Feature: MCP Registry Binding Resolution
  Bot 的 mcp_bindings 透過 Registry 解析為 mcp_servers 配置

  Scenario: HTTP binding 解析為 server config
    Given 一個 Bot 綁定了 HTTP Registry Server
    And Registry 中有對應的 enabled MCP Server
    When 載入 Bot 配置
    Then mcp_servers 應包含 Registry 解析的 HTTP server

  Scenario: stdio binding 解析為 server config
    Given 一個 Bot 綁定了 stdio Registry Server
    And Registry 中有對應的 stdio MCP Server
    When 載入 Bot 配置
    Then mcp_servers 應包含 Registry 解析的 stdio server

  Scenario: disabled Registry Server 被跳過
    Given 一個 Bot 綁定了已停用的 Registry Server
    When 載入 Bot 配置
    Then mcp_servers 應為空
