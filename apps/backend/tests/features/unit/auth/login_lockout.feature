Feature: 登入失敗鎖定 (Login Lockout)
    身為系統
    我想要在同一帳號連續登入失敗達上限時暫時鎖定
    以便公開後台的登入頁不被暴力嘗試

    Background:
        Given 登入鎖定政策為最多 3 次失敗、鎖定 900 秒

    Scenario: 帳號已鎖定時直接拒絕且不驗證密碼
        Given 已註冊使用者 email "user@example.com" 角色 "user" 租戶 "tenant-001"
        And 帳號 "user@example.com" 已被鎖定剩餘 120 秒
        When 我以 email "user@example.com" 密碼 "CorrectPass" 登入
        Then 應拋出帳號鎖定錯誤且 retry_after 為 120
        And 不應驗證密碼

    Scenario: 密碼錯誤累計至上限時鎖定帳號
        Given 已註冊使用者 email "user@example.com" 角色 "user" 租戶 "tenant-001"
        And 帳號 "user@example.com" 已失敗 2 次
        When 我以 email "user@example.com" 密碼 "WrongPassword" 登入
        Then 應拋出帳號鎖定錯誤且 retry_after 為 900
        And 應記錄一次登入失敗

    Scenario: 密碼錯誤但未達上限時回認證失敗
        Given 已註冊使用者 email "user@example.com" 角色 "user" 租戶 "tenant-001"
        When 我以 email "user@example.com" 密碼 "WrongPassword" 登入
        Then 應拋出認證失敗錯誤
        And 應記錄一次登入失敗

    Scenario: 使用者不存在也計入失敗次數
        Given 系統中無 email 為 "nobody@example.com" 的使用者
        When 我以 email "nobody@example.com" 密碼 "AnyPass" 登入
        Then 應拋出認證失敗錯誤
        And 應記錄一次登入失敗

    Scenario: 登入成功時清除失敗計數
        Given 已註冊使用者 email "user@example.com" 角色 "user" 租戶 "tenant-001"
        When 我以 email "user@example.com" 密碼 "CorrectPass" 登入
        Then 應回傳包含 user_id 和 tenant_id 和 role 的 JWT
        And 應清除帳號 "user@example.com" 的失敗計數

    Scenario: 帳號識別不分大小寫與前後空白
        Given 已註冊使用者 email "user@example.com" 角色 "user" 租戶 "tenant-001"
        When 我以 email "  User@Example.com " 密碼 "WrongPassword" 登入
        Then 應以識別 "user@example.com" 記錄登入失敗

    Scenario: 未注入 tracker 時行為不變
        Given 未注入登入嘗試追蹤器
        And 已註冊使用者 email "user@example.com" 角色 "user" 租戶 "tenant-001"
        When 我以 email "user@example.com" 密碼 "WrongPassword" 登入
        Then 應拋出認證失敗錯誤

    Scenario: 帳號鎖定時 login API 回 429 並帶 Retry-After
        Given LoginUseCase 拋出 AccountLockedError retry_after 300
        When 我透過 login API 以 account "user@example.com" 密碼 "AnyPass" 登入
        Then 應拋出 HTTP 429 錯誤且 Retry-After 為 "300"
        And 錯誤訊息不應透露帳號是否存在

    # ── Redis 實作 ──

    Scenario: Redis tracker 未鎖定時 retry_after 為 0
        Given Redis 中鎖定 key 不存在
        When 查詢帳號 "user@example.com" 的 retry_after
        Then retry_after 應為 0

    Scenario: Redis tracker 失敗計數達上限時建立鎖定 key
        Given Redis 失敗計數 INCR 後為 3
        When 記錄帳號 "user@example.com" 一次登入失敗
        Then 應以 900 秒 TTL 建立鎖定 key
        And 應清除失敗計數 key
        And 回傳的 retry_after 應為 900

    Scenario: Redis tracker 失敗計數未達上限時只設定計數 TTL
        Given Redis 失敗計數 INCR 後為 1
        When 記錄帳號 "user@example.com" 一次登入失敗
        Then 不應建立鎖定 key
        And 回傳的 retry_after 應為 0

    Scenario: Redis 不可用時 fail-open
        Given Redis 連線拋出例外
        When 查詢帳號 "user@example.com" 的 retry_after
        Then retry_after 應為 0
        When 記錄帳號 "user@example.com" 一次登入失敗
        Then 回傳的 retry_after 應為 0
