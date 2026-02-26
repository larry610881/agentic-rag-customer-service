Feature: 限流設定管理 (Rate Limit Config)
    身為系統管理員
    我想要管理 API 限流設定
    以便控制各租戶的 API 使用量

    Scenario: 查詢租戶限流設定含預設值 fallback
        Given 系統有全域預設限流設定
        And 租戶 "tenant-001" 有自訂 "rag" 端點群組設定
        When 我查詢租戶 "tenant-001" 的限流設定
        Then 應回傳合併後的設定
        And "rag" 群組應使用租戶自訂值
        And "general" 群組應使用全域預設值

    Scenario: system_admin 成功更新限流設定
        Given 目前使用者角色為 "system_admin"
        When 我更新租戶 "tenant-001" 的 "rag" 端點群組限流為每分鐘 200 次
        Then 設定應成功更新
        And repository 應被呼叫儲存

    Scenario: 非 system_admin 更新限流設定失敗
        Given 目前使用者角色為 "user"
        When 我更新租戶 "tenant-001" 的 "rag" 端點群組限流為每分鐘 200 次
        Then 應拋出權限不足錯誤
