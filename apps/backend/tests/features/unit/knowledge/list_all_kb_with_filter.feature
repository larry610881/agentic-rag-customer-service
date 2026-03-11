Feature: 知識庫列表支援租戶篩選 (List Knowledge Bases with Tenant Filter)
    身為管理員
    我想要在列出所有知識庫時可選擇性依租戶篩選
    以便快速找到特定租戶的知識庫

    Scenario: 不帶 tenant_id 參數時回傳所有知識庫
        Given 系統中有 3 個不同租戶的知識庫
        When 我列出所有知識庫但不指定 tenant_id
        Then 應回傳全部 3 個知識庫

    Scenario: 帶 tenant_id 參數時只回傳該租戶的知識庫
        Given 系統中有 3 個不同租戶的知識庫
        When 我列出所有知識庫並指定 tenant_id 為 "t-001"
        Then 應只回傳 tenant_id 為 "t-001" 的知識庫

    Scenario: 不帶 tenant_id 列出所有 Bot
        Given 系統中有 2 個不同租戶的 Bot
        When 我列出所有 Bot 但不指定 tenant_id
        Then 應回傳全部 2 個 Bot

    Scenario: 帶 tenant_id 列出特定租戶的 Bot
        Given 系統中有 2 個不同租戶的 Bot
        When 我列出所有 Bot 並指定 tenant_id 為 "t-002"
        Then 應只回傳 tenant_id 為 "t-002" 的 Bot
