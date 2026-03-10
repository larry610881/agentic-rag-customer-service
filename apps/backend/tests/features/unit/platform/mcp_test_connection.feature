Feature: MCP Server Connection Test
  測試 MCP Server 連線狀態

  Scenario: 成功連線 HTTP MCP Server
    Given 一個可連線的 MCP Server
    When 我測試連線
    Then 應回傳成功且包含 tools_count

  Scenario: 連線失敗時回傳錯誤
    Given 一個無法連線的 MCP Server
    When 我測試連線
    Then 應回傳失敗且包含錯誤訊息

  Scenario: 成功連線 stdio MCP Server
    Given 一個可連線的 stdio MCP Server
    When 我測試 stdio 連線
    Then 應回傳 stdio 成功結果
