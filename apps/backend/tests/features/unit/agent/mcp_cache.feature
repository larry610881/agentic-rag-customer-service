Feature: MCP 工具載入器
  作為系統，我需要透過 AsyncExitStack 載入 MCP Server 工具並保持 session 存活

  Scenario: 首次載入觸發連線
    Given 一個 MCP 工具載入器
    When 透過 stack 載入 MCP 工具從 "http://mcp.example.com"
    Then 應建立一次連線
    And 應回傳工具列表

  Scenario: 篩選特定工具
    Given 一個 MCP 工具載入器
    And MCP Server 提供 "tool_a" 和 "tool_b" 兩個工具
    When 以 ["tool_a"] 篩選載入
    Then 應只回傳 1 個工具
