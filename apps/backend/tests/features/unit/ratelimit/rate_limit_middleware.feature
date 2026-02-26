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
