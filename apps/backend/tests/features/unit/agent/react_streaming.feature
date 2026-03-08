Feature: ReAct Agent Streaming 事件
  作為系統，我需要驗證 ReAct Agent streaming 正確產出事件序列

  Scenario: 單次工具呼叫的事件序列
    Given 一個配置了 RAG 工具的 Streaming ReAct Agent
    And LLM 會先呼叫工具再生成回答
    When 以 streaming 模式處理用戶訊息
    Then 事件序列應包含 tool_calls 事件
    And 事件序列應包含 token 事件
    And 最後一個事件應為 done

  Scenario: 多輪工具呼叫的事件序列
    Given 一個配置了多個工具的 Streaming ReAct Agent
    And LLM 會呼叫兩次工具後再生成回答
    When 以 streaming 模式處理用戶訊息
    Then 事件序列應包含至少 2 個 tool_calls 事件
    And 事件序列應包含 token 事件
    And 最後一個事件應為 done
