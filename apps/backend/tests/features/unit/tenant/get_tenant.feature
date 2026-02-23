Feature: 查詢租戶 (Get Tenant)
    身為系統管理員
    我想要查詢租戶資訊
    以便確認租戶的狀態與設定

    Scenario: 成功查詢存在的租戶
        Given 系統中已存在 ID 為 "t-001" 的租戶 "Acme Corp"
        When 我以 ID "t-001" 查詢租戶
        Then 應回傳租戶資訊
        And 回傳的租戶名稱應為 "Acme Corp"

    Scenario: 查詢不存在的租戶應失敗
        Given 系統中不存在 ID 為 "t-999" 的租戶
        When 我以 ID "t-999" 查詢租戶
        Then 應拋出租戶不存在錯誤
