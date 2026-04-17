Feature: Trace Tool Payload 完整記錄
  Tool 執行的原始 payload（含 contact 等 rich content）
  應完整保留在 ExecutionNode.metadata 中，
  讓觀測性介面能回溯 tool 實際傳出的資料

  Scenario: Tool 輸出為 JSON dict 時存入 metadata.tool_output
    Given 一個會回傳 JSON dict 的 tool node
    When ReactAgentService 記錄 tool trace
    Then 對應 ExecutionNode 的 metadata 應包含完整 tool_output dict

  Scenario: Tool 輸出為純文字時不寫入 tool_output
    Given 一個回傳純文字結果的 tool node
    When ReactAgentService 記錄 tool trace
    Then 對應 ExecutionNode 的 metadata 不應包含 tool_output 欄位

  Scenario: Contact event 寫入 trace node metadata
    Given 一個 transfer_to_human tool 回傳含 contact 的 payload
    When ReactAgentService 串流處理 tool 結果
    Then 對應 ExecutionNode 的 metadata 應包含 contact 欄位
