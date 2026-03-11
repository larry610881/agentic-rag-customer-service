Feature: 錯誤回報機制 (Error Reporter)
    身為開發者
    我想要一個統一的錯誤回報機制
    以便將 unhandled exception 資訊記錄到 request log

    Scenario: ErrorContext 正確封裝錯誤資訊
        Given 一個 HTTP 請求發生例外
        When 我建立 ErrorContext
        Then ErrorContext 應包含 request_id, tenant_id, method, path, status_code

    Scenario: ErrorContext 是不可變的
        Given 一個已建立的 ErrorContext
        When 我嘗試修改其屬性
        Then 應拋出 FrozenInstanceError

    Scenario: ContextVar 可設定與讀取 captured_error
        When 我設定 captured_error 為一個錯誤訊息
        Then 我應能透過 get_captured_error 讀取該訊息

    Scenario: ContextVar 預設值為 None
        When 我在未設定的情況下讀取 captured_error
        Then 應回傳 None
