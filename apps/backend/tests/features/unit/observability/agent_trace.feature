Feature: Agent 執行追蹤
  作為系統，我需要追蹤每次 Agent 執行的完整編排鏈路以支援可觀測性

  Scenario: 完整 ReAct 追蹤鏈路記錄
    Given 一個 Agent 追蹤收集器已啟動 模式 "react" 租戶 "T001"
    When 新增 user_input 節點 起始 0ms 結束 0ms
    And 新增 agent_llm 節點 起始 5ms 結束 120ms 含 token 用量
    And 新增 tool_call 節點 "rag_query" 起始 121ms 結束 350ms 掛在上一個 agent_llm 下
    And 新增 final_response 節點 起始 355ms 結束 355ms
    And 完成追蹤總耗時 360ms
    Then 追蹤記錄應包含 4 個節點
    And 追蹤記錄模式應為 "react"
    And 追蹤記錄總耗時應為 360ms
    And tool_call 節點的 parent 應為 agent_llm 節點

  Scenario: Supervisor 追蹤鏈路記錄
    Given 一個 Agent 追蹤收集器已啟動 模式 "supervisor" 租戶 "T002"
    When 新增 user_input 節點 起始 0ms 結束 0ms
    And 新增 supervisor_dispatch 節點 "main_worker" 起始 1ms 結束 1ms
    And 新增 worker_execution 節點 "main_worker" 起始 2ms 結束 200ms
    And 新增 final_response 節點 起始 201ms 結束 201ms
    And 完成追蹤總耗時 210ms
    Then 追蹤記錄應包含 4 個節點
    And 追蹤記錄模式應為 "supervisor"

  Scenario: Finish 清空 ContextVar 並回傳追蹤
    Given 一個 Agent 追蹤收集器已啟動 模式 "react" 租戶 "T001"
    When 新增 user_input 節點 起始 0ms 結束 0ms
    And 完成追蹤總耗時 100ms
    Then 應回傳追蹤記錄且 ContextVar 已清空

  Scenario: 未啟動收集器時 add_node 不報錯
    When 在未啟動的收集器上新增節點
    Then 應回傳空字串且不報錯

  Scenario: ExecutionNode 序列化為 dict
    Given 一個包含 metadata 的 ExecutionNode
    When 序列化為 dict
    Then 應包含所有欄位且 metadata 正確
