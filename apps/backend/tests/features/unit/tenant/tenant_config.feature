Feature: 租戶設定管理 (Tenant Configuration Management)
    身為系統管理員
    我想要管理租戶的設定（如月 Token 上限）
    以便控制各租戶的資源使用

    Scenario: 設定每月 Token 上限
        Given 租戶 "窩廚房" 存在且無 Token 上限
        When 我設定月 Token 上限為 500000
        Then 租戶的 monthly_token_limit 應為 500000

    Scenario: 清除 Token 上限
        Given 租戶 "窩廚房" 有月 Token 上限 500000
        When 我將月 Token 上限設為 null
        Then 租戶的 monthly_token_limit 應為 None

    Scenario: Tenant entity 預設無 Token 上限
        When 我建立一個新的 Tenant entity
        Then monthly_token_limit 應為 None
