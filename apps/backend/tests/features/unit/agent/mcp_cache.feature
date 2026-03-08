Feature: MCP 工具快取
  作為系統，我需要快取 MCP Server 的工具載入以避免重複連線

  Scenario: 首次載入觸發連線
    Given 一個空的 MCP 快取載入器
    When 載入 MCP 工具從 "http://mcp.example.com"
    Then 應建立一次 SSE 連線
    And 應回傳工具列表

  Scenario: 快取命中不重新連線
    Given 一個已快取 "http://mcp.example.com" 工具的載入器
    When 再次載入 MCP 工具從 "http://mcp.example.com"
    Then 不應建立新的 SSE 連線
    And 應回傳相同的工具列表

  Scenario: 快取過期後重新載入
    Given 一個已快取但 TTL 已過期的載入器
    When 載入 MCP 工具從 "http://mcp.example.com"
    Then 應建立新的 SSE 連線

  Scenario: 篩選特定工具
    Given 一個已快取包含 "tool_a" 和 "tool_b" 的載入器
    When 以 ["tool_a"] 篩選載入
    Then 應只回傳 1 個工具
