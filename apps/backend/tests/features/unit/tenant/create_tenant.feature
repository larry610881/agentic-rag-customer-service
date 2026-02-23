Feature: 建立租戶 (Create Tenant)
    身為系統管理員
    我想要建立新租戶
    以便為客戶提供獨立的服務環境

    Scenario: 成功建立新租戶
        Given 系統中尚未有名稱為 "Acme Corp" 的租戶
        When 我以名稱 "Acme Corp" 和方案 "professional" 建立租戶
        Then 租戶應成功建立
        And 租戶名稱應為 "Acme Corp"
        And 租戶方案應為 "professional"

    Scenario: 建立重複名稱的租戶應失敗
        Given 系統中已有名稱為 "Acme Corp" 的租戶
        When 我以名稱 "Acme Corp" 和方案 "starter" 建立租戶
        Then 應拋出重複租戶錯誤
