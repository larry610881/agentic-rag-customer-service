Feature: 滑動視窗限流器 (Sliding Window Rate Limiter)
    身為系統
    我想要使用滑動視窗計數器限制 API 請求
    以便防止 API 濫用

    Scenario: 限制內請求允許通過
        Given 限流設定為每分鐘 10 次
        And 目前視窗內有 5 次請求
        When 檢查限流
        Then 請求應被允許
        And 剩餘次數應為 4

    Scenario: 超過限制的請求被拒絕
        Given 限流設定為每分鐘 10 次
        And 目前視窗內有 10 次請求
        When 檢查限流
        Then 請求應被拒絕
        And retry_after 應大於 0

    Scenario: Redis 斷線時降級放行
        Given 限流設定為每分鐘 10 次
        And Redis 連線已斷開
        When 檢查限流
        Then 請求應被允許
