Feature: 租戶資料隔離 (Tenant Isolation)
    身為系統架構師
    我想要確保租戶之間的資料完全隔離
    以便保障各租戶的資料安全

    Scenario: 租戶 A 不可見租戶 B 的知識庫
        Given 租戶 "tenant-a" 有知識庫 "A的知識庫"
        And 租戶 "tenant-b" 有知識庫 "B的知識庫"
        When 我以租戶 "tenant-a" 身分列出知識庫
        Then 應只回傳 1 個知識庫
        And 回傳的知識庫名稱應包含 "A的知識庫"
        And 回傳的知識庫名稱不應包含 "B的知識庫"

    Scenario: 租戶 B 不可見租戶 A 的知識庫
        Given 租戶 "tenant-a" 有知識庫 "A的知識庫"
        And 租戶 "tenant-b" 有知識庫 "B的知識庫"
        When 我以租戶 "tenant-b" 身分列出知識庫
        Then 應只回傳 1 個知識庫
        And 回傳的知識庫名稱應包含 "B的知識庫"
        And 回傳的知識庫名稱不應包含 "A的知識庫"
