Feature: 使用者自助變更密碼 (Change Password)
    身為已登入的租戶使用者
    我想要自行變更登入密碼（需驗證舊密碼）
    以便不需要透過管理員即可更換 admin 發的預設密碼或定期變更

    Background:
        Given 系統中存在使用者 "u-1" email "alice@acme.com" 密碼 "OldPass123" 角色 "user" 租戶 "t-1"

    Scenario: 舊密碼正確 — 成功變更密碼
        When 我以 user_id "u-1" 舊密碼 "OldPass123" 新密碼 "NewPass456" 變更密碼
        Then 變更應成功
        And 使用者 "u-1" 的 hashed_password 應更新為 "NewPass456" 的 hash

    Scenario: 舊密碼錯誤 — 拒絕變更
        When 我以 user_id "u-1" 舊密碼 "WrongOldPass" 新密碼 "NewPass456" 變更密碼
        Then 應拋出認證失敗錯誤
        And 使用者 "u-1" 的 hashed_password 不應被修改

    Scenario: 使用者不存在 — 拋出 NotFound
        When 我以 user_id "u-nonexistent" 舊密碼 "OldPass123" 新密碼 "NewPass456" 變更密碼
        Then 應拋出 EntityNotFoundError

    Scenario: 新密碼與舊密碼相同 — 拒絕變更
        When 我以 user_id "u-1" 舊密碼 "OldPass123" 新密碼 "OldPass123" 變更密碼
        Then 應拋出 SameAsOldPasswordError
