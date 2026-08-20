Feature: Bot 設定快照與 Overlay 回朔合併
  作為版本化底座，快照必須只含白名單行為欄位，
  憑證與外觀營運欄位絕不入快照；回朔採 overlay 合併。

  Scenario: 快照只包含白名單行為欄位
    Given 一個完整設定的 Bot（含憑證與 widget 外觀欄位）
    When 對該 Bot 取設定快照
    Then 快照包含 prompt 類與 LLM 參數與 RAG 檢索與 Agent 行為欄位
    And 快照不包含 line_channel_secret 與 line_channel_access_token
    And 快照不包含 widget 外觀欄位與 is_active
    And 快照不包含 eval 觀測設定欄位

  Scenario: 快照中的 mcp_bindings 剝除 env_values
    Given 一個綁定了 MCP 且 env_values 含加密金鑰的 Bot
    When 對該 Bot 取設定快照
    Then 快照的 mcp_bindings 只含 registry_id 與 enabled_tools
    And 快照的 mcp_bindings 不含 env_values

  Scenario: changed_fields 反映兩份快照的差異
    Given 一個完整設定的 Bot（含憑證與 widget 外觀欄位）
    When 修改 base_prompt 與 temperature 後比較新舊快照
    Then changed_fields 恰為 base_prompt 與 llm_params.temperature

  Scenario: Overlay 套用快照到 Bot
    Given 一個完整設定的 Bot（含憑證與 widget 外觀欄位）
    And 一份 base_prompt 為 "舊版提示詞" 且 temperature 為 0.9 的快照
    When 將快照 overlay 套用到該 Bot
    Then Bot 的 base_prompt 為 "舊版提示詞" 且 temperature 為 0.9
    And Bot 的憑證欄位維持原值

  Scenario: Overlay 對快照缺少的欄位保留現值
    Given 一個完整設定的 Bot（含憑證與 widget 外觀欄位）
    And 一份只含 base_prompt 的部分快照（模擬舊 schema 版本）
    When 將快照 overlay 套用到該 Bot
    Then Bot 的 base_prompt 為快照值
    And 其餘白名單欄位維持現值
    And 回報 skipped_fields 列出快照缺少的欄位

  Scenario: Overlay 還原 mcp_bindings 時保留現行 env_values
    Given 一個綁定了 MCP 且 env_values 含加密金鑰的 Bot
    And 一份含相同 registry_id 的 mcp_bindings 快照
    When 將快照 overlay 套用到該 Bot
    Then Bot 的 mcp_bindings env_values 維持現行加密值
