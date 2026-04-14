Feature: Bot Worker 配置管理
  作為系統，我需要管理 Bot 的 Sub-agent Worker 配置

  Scenario: 建立 Worker 並回傳完整配置
    Given 一個 Worker 配置 Repository
    When 建立名為 "客訴處理" 的 Worker 屬於 Bot "bot-001"
    Then Worker 應成功建立且名稱為 "客訴處理"
    And Worker 的 bot_id 應為 "bot-001"

  Scenario: 列出 Bot 的所有 Workers
    Given 一個 Worker 配置 Repository
    And Bot "bot-001" 已有 2 個 Workers
    When 查詢 Bot "bot-001" 的 Workers
    Then 應回傳 2 個 Workers

  Scenario: 更新 Worker 的 LLM 模型
    Given 一個 Worker 配置 Repository
    And 已建立一個 Worker
    When 更新 Worker 的 llm_model 為 "claude-haiku-4-5-20251001"
    Then Worker 的 llm_model 應為 "claude-haiku-4-5-20251001"

  Scenario: 刪除 Worker
    Given 一個 Worker 配置 Repository
    And 已建立一個 Worker
    When 刪除該 Worker
    Then 查詢該 Worker 應回傳 None

  Scenario: Worker 可配置 MCP tool 子集
    Given 一個 Worker 配置 Repository
    When 建立 Worker 並指定 enabled_mcp_ids 為 ["mcp-001", "mcp-002"]
    Then Worker 的 enabled_mcp_ids 應包含 2 個 ID

  Scenario: Worker 可指定知識庫
    Given 一個 Worker 配置 Repository
    When 建立 Worker 並指定 knowledge_base_ids 為 ["kb-001", "kb-002"]
    Then Worker 的 knowledge_base_ids 應包含 2 個 ID
