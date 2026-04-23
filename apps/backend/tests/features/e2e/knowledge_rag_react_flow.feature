Feature: 知識庫 RAG ReAct Agent 完整旅程
  身為租戶管理員，我配置 ReAct 模式的 Bot，
  Agent 透過 RAG 工具查詢知識庫並產生回答。

  Scenario: ReAct Agent 呼叫 RAG 工具並回答
    Given 已建立租戶 "ReAct Corp" 並取得 token 並啟用 react
    And 已建立知識庫 "商品FAQ"
    And 已上傳文件 "退貨流程.txt" 到知識庫
    And 已建立 Bot "ReAct客服" 綁定知識庫 agent_mode 為 "react"
    When 我透過 Bot 發送對話 "退貨流程是什麼？"
    Then 回應狀態碼為 200
    And 回答應非空
    And tool_calls 應包含 "rag_query"

  # Scenario: ReAct Agent audit_mode off 不記錄工具呼叫
  # 已刪除（S-KB-Followup.1）：audit_mode 欄位從未在 Bot entity 實作，
  # 此 scenario 對應的 setup_bot_audit step 也沒 pass audit_mode 給 create_bot，
  # 整個 scenario 在測從未實作的功能。若未來實作 Bot.audit_mode 再補回。

  Scenario: ReAct Agent max_tool_calls 限制
    Given 已建立租戶 "MaxCall Corp" 並取得 token 並啟用 react
    And 已建立知識庫 "商品FAQ"
    And 已建立 Bot "ReAct客服" 綁定知識庫 agent_mode 為 "react" max_tool_calls 為 1
    When 我透過 Bot 發送對話 "退貨流程是什麼？"
    Then 回應狀態碼為 200
    And tool_calls 數量不應超過 1
