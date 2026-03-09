Feature: Bot API Integration
  使用真實 DB 驗證 Bot CRUD API（含 JWT 認證）

  Background:
    Given 已登入為租戶 "Bot Corp"

  Scenario: 成功建立 Bot
    When 我送出認證 POST /api/v1/bots 名稱為 "客服機器人"
    Then 回應狀態碼為 201
    And 回應包含 bot name 為 "客服機器人"

  Scenario: 查詢 Bot 列表
    Given 已建立 Bot "Bot A"
    And 已建立 Bot "Bot B"
    When 我送出認證 GET /api/v1/bots
    Then 回應狀態碼為 200
    And 回應包含 2 個 Bot

  Scenario: 查詢單一 Bot
    Given 已建立 Bot "詳情 Bot"
    When 我用該 Bot ID 送出 GET /api/v1/bots/{id}
    Then 回應狀態碼為 200
    And 回應包含 bot name 為 "詳情 Bot"

  Scenario: 更新 Bot
    Given 已建立 Bot "舊名稱"
    When 我用該 Bot ID 送出 PUT /api/v1/bots/{id} 名稱為 "新名稱"
    Then 回應狀態碼為 200
    And 回應包含 bot name 為 "新名稱"

  Scenario: 刪除 Bot
    Given 已建立 Bot "待刪除"
    When 我用該 Bot ID 送出 DELETE /api/v1/bots/{id}
    Then 回應狀態碼為 204

  Scenario: 查詢不存在的 Bot 回傳 404
    When 我送出認證 GET /api/v1/bots/00000000-0000-0000-0000-000000000000
    Then 回應狀態碼為 404

  Scenario: 未認證時拒絕存取
    When 我不帶 token 送出 GET /api/v1/bots
    Then 回應狀態碼為 401

  Scenario: 建立 Bot 並綁定知識庫
    Given 已建立知識庫 "FAQ"
    When 我送出認證 POST /api/v1/bots 名稱為 "KB Bot" 綁定知識庫
    Then 回應狀態碼為 201
    And 回應包含綁定的知識庫 ID

  Scenario: 建立 Bot 含 MCP Servers 設定
    When 我送出認證 POST /api/v1/bots 含 MCP 設定
    Then 回應狀態碼為 201
    And 回應包含 mcp_servers 陣列長度為 2
    And 回應 mcp_servers 第 1 個 URL 為 "http://localhost:9000/mcp"
    And 回應 mcp_servers 第 2 個 name 為 "crm"

  Scenario: 建立 Bot 後重新查詢 — MCP 欄位完整保留
    When 我送出認證 POST /api/v1/bots 含 MCP 設定
    Then 回應狀態碼為 201
    When 我用該回應 Bot ID 送出 GET /api/v1/bots/{id}
    Then 回應狀態碼為 200
    And 回應包含 mcp_servers 陣列長度為 2
    And 回應 mcp_servers 第 1 個 enabled_tools 包含 "search_products"

  Scenario: 更新 Bot 的 MCP Servers
    Given 已建立 Bot "MCP Bot"
    When 我用該 Bot ID 送出 PUT 更新 mcp_servers
    Then 回應狀態碼為 200
    And 回應包含 mcp_servers 陣列長度為 1
    And 回應 mcp_servers 第 1 個 name 為 "new-server"

  Scenario: 建立 Bot — 所有欄位完整 round-trip
    When 我送出認證 POST /api/v1/bots 含完整欄位
    Then 回應狀態碼為 201
    And 回應欄位 agent_mode 為 "react"
    And 回應欄位 audit_mode 為 "full"
    And 回應欄位 max_tool_calls 為 10
    And 回應包含 mcp_servers 陣列長度為 1
