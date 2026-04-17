Feature: Tool Label Resolution
  前端顯示 tool 呼叫時需要中文 label。
  Backend 統一在 resolve_tool_label() 處理，
  前端透過 tool_calls event 帶的 label 欄位直接顯示，
  避免前後端維護兩份 name → label 對應表。

  Scenario: 內建工具由 BUILT_IN_TOOL_DEFAULTS 解析 label
    Given 內建工具清單包含 "rag_query" 對應 "知識庫查詢"
    When 呼叫 resolve_tool_label("rag_query")
    Then 應回傳 "知識庫查詢"

  Scenario: MCP 工具由 MCP registry 解析 label
    Given MCP registry 含工具 "search_products" 對應 label "查詢商品"
    When 呼叫 resolve_tool_label("search_products") 並附上 registry
    Then 應回傳 "查詢商品"

  Scenario: 未知工具 fallback 回原始 name
    Given 內建工具清單不含 "custom_tool"
    And MCP registry 也不含 "custom_tool"
    When 呼叫 resolve_tool_label("custom_tool")
    Then 應回傳 "custom_tool"
