Feature: 請求日誌增強 (Request Log Enhancement)
    身為系統管理員
    我想要請求日誌包含租戶資訊與錯誤細節
    以便快速定位問題來源

    Scenario: 從 user_access JWT 提取 tenant_id
        Given 一個 user_access 類型的 JWT token 包含 tenant_id "t-001"
        When 我解析該 token 的 tenant_id
        Then 應回傳 "t-001"

    Scenario: 從 tenant_access JWT 提取 tenant_id
        Given 一個 tenant_access 類型的 JWT token 包含 sub "t-002"
        When 我解析該 token 的 tenant_id
        Then 應回傳 "t-002"

    Scenario: 無 Authorization header 時 tenant_id 為 None
        Given 一個沒有 Authorization header 的請求
        When 我解析該 token 的 tenant_id
        Then 應回傳 None

    Scenario: 無效 JWT 時 tenant_id 為 None
        Given 一個包含無效 JWT 的請求
        When 我解析該 token 的 tenant_id
        Then 應回傳 None

    Scenario: write_request_log 接受 tenant_id 和 error_detail 參數
        Given write_request_log 函式接受 tenant_id 和 error_detail 參數
        Then 函式簽名應包含 tenant_id 和 error_detail 可選參數
