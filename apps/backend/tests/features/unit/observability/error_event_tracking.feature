Feature: Error Event Tracking
  錯誤事件追蹤系統 — 捕捉、記錄、查詢、標記已處理

  Scenario: 後端錯誤被捕捉並建立 error_event
    Given 一個 500 錯誤發生在路徑 "/api/v1/agent/chat" 方法 "POST"
    When 系統呼叫 ReportErrorUseCase 回報錯誤
    Then 應建立一個 error_event 記錄
    And fingerprint 應為非空字串

  Scenario: 前端錯誤透過公開 API 回報成功
    Given 前端發送一個 TypeError 錯誤報告
    When 系統呼叫 ReportErrorUseCase 回報前端錯誤
    Then 應建立一個 source 為 "frontend" 的 error_event

  Scenario: Fingerprint 正規化路徑中的 UUID 和數字 ID
    Given 路徑 "/api/v1/conversations/550e8400-e29b-41d4-a716-446655440000/messages"
    When 計算 fingerprint
    Then 正規化路徑應為 "/api/v1/conversations/:id/messages"

  Scenario: 依 resolved 狀態過濾列表
    Given 系統中有 3 個 error_event 其中 1 個已標記 resolved
    When 查詢 resolved=false 的 error_event 列表
    Then 應回傳 2 個 error_event

  Scenario: 標記 error event 為已處理
    Given 系統中有一個未處理的 error_event
    When 標記該 error_event 為已處理
    Then error_event 的 resolved 應為 true
    And resolved_at 應為非空
    And resolved_by 應為 "admin@test.com"

  Scenario: 重複 fingerprint 不重複寄信（throttle）
    Given 通知渠道已啟用且 throttle 為 15 分鐘
    And throttle 服務回報該 fingerprint 已被節流
    When 同一 fingerprint 的新錯誤發生
    Then 不應觸發新的通知
