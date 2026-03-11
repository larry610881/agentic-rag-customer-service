Feature: MCP Binding env_values Encryption
  Bot mcp_bindings 中的 env_values 需加密存儲、使用時解密

  Scenario: 建立 Bot 時加密 env_values
    Given 一個帶有 MCP binding env_values 的建立指令
    When 執行 CreateBotUseCase
    Then 存入 Repository 的 env_values 值應為加密字串

  Scenario: Agent 處理訊息時解密 env_values
    Given 一個 Bot 帶有加密的 mcp_binding env_values
    When SendMessageUseCase 解析 mcp_bindings
    Then URL 模板應使用解密後的值替換
