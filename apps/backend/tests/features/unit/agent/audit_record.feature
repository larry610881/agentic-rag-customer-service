Feature: Audit 記錄模式
  作為系統管理員，我需要控制工具呼叫的記錄詳細程度

  Scenario: Minimal 模式只記錄基本資訊
    Given 一個 audit_mode 為 "minimal" 的設定
    When ReAct Agent 處理一次工具呼叫
    Then tool_calls 應包含 tool_name
    And tool_calls 不應包含 tool_input

  Scenario: Full 模式記錄完整資訊
    Given 一個 audit_mode 為 "full" 的設定
    When ReAct Agent 處理一次工具呼叫
    Then tool_calls 應包含 tool_name
    And tool_calls 應包含 tool_input
    And tool_calls 應包含 iteration

  Scenario: Bot 預設使用 minimal 模式
    Given 一個未設定 audit_mode 的 Bot
    Then Bot 的 audit_mode 應為 "minimal"
