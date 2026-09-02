Feature: 限流中介層 (Rate Limit Middleware)
    身為系統
    我想要在 API 層攔截超過限額的請求
    以便保護後端服務

    Scenario: 受保護端點 per-tenant 限流觸發 429
        Given 限流中介層已設定
        And 租戶 "tenant-001" 的 "rag" 端點群組已超過限額
        When 租戶 "tenant-001" 請求 "/api/v1/rag/query"
        Then 回應狀態碼應為 429
        And 回應應包含 Retry-After header

    Scenario: 公開端點 per-IP 限流觸發 429
        Given 限流中介層已設定
        And IP "192.168.1.1" 的 "general" 端點群組已超過限額
        When IP "192.168.1.1" 請求 "/api/v1/tenants"
        Then 回應狀態碼應為 429

    Scenario: per-user 限流觸發
        Given 限流中介層已設定
        And 租戶 "tenant-001" 的 "rag" 端點群組未超過限額
        And 使用者 "user-001" 的 per-user 限額已超過
        When 使用者 "user-001" 租戶 "tenant-001" 請求 "/api/v1/rag/query"
        Then 回應狀態碼應為 429

    Scenario: 豁免端點不受限流
        Given 限流中介層已設定
        When 請求 "/health"
        Then 請求應直接通過不檢查限流

    Scenario: 登入端點歸入 auth 群組並以 IP 限流
        Given 限流中介層已設定
        And IP "203.0.113.9" 的 "auth" 端點群組已超過限額
        When IP "203.0.113.9" 以 POST 請求 "/api/v1/auth/login"
        Then 回應狀態碼應為 429
        And 限流 key 應包含端點群組 "auth"

    Scenario: X-Forwarded-For 存在時以最後一段作為 client IP
        Given 限流中介層已設定
        When 帶 X-Forwarded-For "198.51.100.7, 203.0.113.9" 以 POST 請求 "/api/v1/auth/login"
        Then 限流 key 應包含 IP "203.0.113.9"
        And 限流 key 不應包含 IP "198.51.100.7"

    Scenario: refresh 端點維持豁免
        Given 限流中介層已設定
        When 以 POST 請求 "/api/v1/auth/refresh"
        Then 請求應直接通過不檢查限流

    Scenario: auth 群組無 DB 設定時 fallback 每分鐘 10 次
        Given 限流設定載入器無快取且 DB 無 "auth" 群組設定
        When 載入 "auth" 群組設定
        Then requests_per_minute 應為 10

    Scenario: general 群組無 DB 設定時維持既有 fallback
        Given 限流設定載入器無快取且 DB 無 "general" 群組設定
        When 載入 "general" 群組設定
        Then requests_per_minute 應為 200
