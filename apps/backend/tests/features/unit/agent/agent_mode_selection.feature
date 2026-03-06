Feature: Agent Mode Selection
  作為系統，我需要根據 Bot 的 agent_mode 設定和 Tenant 的 allowed_agent_modes
  來選擇正確的 Agent Service 處理訊息

  Scenario: 預設使用 Router 模式
    Given 一個 Bot 設定 agent_mode 為 "router"
    And Tenant 允許的 agent_modes 為 ["router"]
    When 發送訊息時解析 Agent Service
    Then 應使用 Router Agent Service

  Scenario: Tenant 允許 ReAct 模式時使用 ReAct
    Given 一個 Bot 設定 agent_mode 為 "react"
    And Tenant 允許的 agent_modes 為 ["router", "react"]
    When 發送訊息時解析 Agent Service
    Then 應使用 ReAct Agent Service

  Scenario: Tenant 不允許 ReAct 時 Fallback 到 Router
    Given 一個 Bot 設定 agent_mode 為 "react"
    And Tenant 允許的 agent_modes 為 ["router"]
    When 發送訊息時解析 Agent Service
    Then 應使用 Router Agent Service

  Scenario: ReAct 模式尚未實作時回傳錯誤
    Given 一個 Bot 設定 agent_mode 為 "react"
    And Tenant 允許的 agent_modes 為 ["router", "react"]
    And ReAct Agent Service 未註冊
    When 發送訊息時解析 Agent Service
    Then 應拋出 DomainException 錯誤 "ReAct agent mode is not available"
