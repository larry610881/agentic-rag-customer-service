Feature: 使用者註冊 (User Registration)
    身為系統管理員或租戶管理員
    我想要註冊新使用者
    以便讓使用者登入系統

    Scenario: 成功註冊一般使用者
        Given 系統中尚未有 email 為 "user@example.com" 的使用者
        And 存在租戶 "tenant-001"
        When 我以 email "user@example.com" 密碼 "SecurePass123" 角色 "user" 租戶 "tenant-001" 註冊
        Then 使用者應成功建立
        And 使用者 email 應為 "user@example.com"
        And 使用者角色應為 "user"
        And 使用者租戶應為 "tenant-001"

    Scenario: 成功註冊系統管理員
        Given 系統中尚未有 email 為 "admin@example.com" 的使用者
        When 我以 email "admin@example.com" 密碼 "AdminPass456" 角色 "system_admin" 無租戶 註冊
        Then 使用者應成功建立
        And 使用者 email 應為 "admin@example.com"
        And 使用者角色應為 "system_admin"
        And 使用者租戶應為空

    Scenario: 重複 email 註冊失敗
        Given 系統中已有 email 為 "existing@example.com" 的使用者
        When 我以 email "existing@example.com" 密碼 "AnyPass789" 角色 "user" 租戶 "tenant-001" 註冊
        Then 應拋出重複使用者錯誤

    Scenario: tenant_admin 缺少 tenant_id 註冊失敗
        Given 系統中尚未有 email 為 "ta@example.com" 的使用者
        When 我以 email "ta@example.com" 密碼 "Pass123456" 角色 "tenant_admin" 無租戶 註冊
        Then 應拋出缺少租戶錯誤
