Feature: MCP Server Tool Discovery
  探索 MCP Server 提供的工具列表

  Scenario: 探索 HTTP MCP Server 工具
    Given 一個可連線的 HTTP MCP Server
    When 我執行工具探索
    Then 應回傳工具列表

  Scenario: 探索後寫回註冊庫
    Given 一個可連線的 HTTP MCP Server 且已在註冊庫中
    When 我執行工具探索並指定 server_id
    Then 註冊庫中的 available_tools 應被更新

  Scenario: 探索 stdio MCP Server 工具
    Given 一個可連線的 stdio MCP Server
    When 我執行 stdio 工具探索
    Then 應回傳 stdio 工具列表
