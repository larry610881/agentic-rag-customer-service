Feature: Tenant Permission Management
    系統管理員可設定每個租戶的功能權限

    Scenario: 設定有效的 Agent 模式
        Given 一個 starter 方案的租戶
        When 系統管理員設定 allowed_agent_modes 為 router 和 react
        Then 設定應成功儲存
        And allowed_agent_modes 應包含 router 和 react

    Scenario: 設定無效的 Agent 模式被拒絕
        Given 一個 starter 方案的租戶
        When 系統管理員設定 allowed_agent_modes 包含無效值 invalid_mode
        Then allowed_agent_modes 不應被變更

