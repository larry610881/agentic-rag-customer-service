Feature: JWT 向後相容 (JWT Backward Compatibility)
    身為系統開發者
    我想確保新舊 JWT 格式都能被正確解析
    以便不中斷現有功能

    Scenario: 舊版 tenant_access JWT 仍可解析
        Given 一個 type 為 "tenant_access" 的舊版 JWT 包含 tenant_id "tenant-001"
        When 解析此 JWT
        Then 應取得 tenant_id "tenant-001"
        And user_id 應為空
        And role 應為空

    Scenario: 新版 user_access JWT 解析完整資訊
        Given 一個 type 為 "user_access" 的新版 JWT 包含 user_id "user-001" tenant_id "tenant-001" role "user"
        When 解析此 JWT
        Then 應取得 tenant_id "tenant-001"
        And 應取得 user_id "user-001"
        And 應取得 role "user"
