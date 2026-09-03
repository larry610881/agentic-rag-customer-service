Feature: 使用者登入 (User Login)
    身為已註冊使用者
    我想要用 email 和密碼登入
    以便取得含 user_id、tenant_id、role 的 JWT

    Scenario: 成功登入
        Given 已註冊使用者 email "user@example.com" 角色 "user" 租戶 "tenant-001"
        When 我以 email "user@example.com" 密碼 "CorrectPass" 登入
        Then 應回傳包含 user_id 和 tenant_id 和 role 的 JWT
        And JWT type 應為 "user_access"

    Scenario: 密碼錯誤
        Given 已註冊使用者 email "user@example.com" 角色 "user" 租戶 "tenant-001"
        When 我以 email "user@example.com" 密碼 "WrongPassword" 登入
        Then 應拋出認證失敗錯誤

    Scenario: 使用者不存在
        Given 系統中無 email 為 "nobody@example.com" 的使用者
        When 我以 email "nobody@example.com" 密碼 "AnyPass" 登入
        Then 應拋出認證失敗錯誤

    Scenario: login API 以 email/password 成功登入
        Given LoginUseCase 驗證成功回傳 token
        When 我透過 login API 以 account "user@example.com" 密碼 "CorrectPass" 登入
        Then 應回傳 LoginUseCase 的 token

    Scenario: login API 密碼錯誤回傳 401
        Given LoginUseCase 拋出 AuthenticationError
        When 我透過 login API 以 account "user@example.com" 密碼 "WrongPass" 登入
        Then 應拋出 HTTP 401 錯誤

    Scenario: 租戶名稱免密碼登入已移除，一律走 email/password（Issue #67 P5）
        Given LoginUseCase 拋出 AuthenticationError
        When 我透過 login API 以 account "Some Tenant" 密碼 "any" 登入
        Then 應拋出 HTTP 401 錯誤
