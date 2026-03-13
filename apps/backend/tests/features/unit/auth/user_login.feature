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

    Scenario: Production 模式 email/password 成功登入
        Given app_env 為 "production"
        And LoginUseCase 驗證成功回傳 token
        When 我透過 login API 以 account "user@example.com" 密碼 "CorrectPass" 登入
        Then 應回傳 LoginUseCase 的 token
        And 不應呼叫 tenant_repo.find_by_name

    Scenario: Production 模式密碼錯誤回傳 401
        Given app_env 為 "production"
        And LoginUseCase 拋出 AuthenticationError
        When 我透過 login API 以 account "user@example.com" 密碼 "WrongPass" 登入
        Then 應拋出 HTTP 401 錯誤

    Scenario: Dev 模式 tenant 不存在 fallback 到 email/password
        Given app_env 為 "development"
        And tenant_repo.find_by_name 回傳 None
        And LoginUseCase 驗證成功回傳 token
        When 我透過 login API 以 account "unknown_tenant" 密碼 "Pass123" 登入
        Then 應回傳 LoginUseCase 的 token
