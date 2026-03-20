Feature: Background Task Error Tracking (背景任務錯誤追蹤)
    背景任務失敗時應自動寫入 error_events 表
    讓 Admin Dashboard 可以即時看到這些錯誤

  Scenario: Background task 失敗時寫入 error_events
    Given 一個會拋出 ValueError 的 async 任務
    When 透過 safe_background_task 執行該任務並追蹤錯誤
    Then write_error_event 應被呼叫一次
    And error_detail 應為 "ValueError: bad input"
    And method 應為 "BACKGROUND"
    And path 應為 "background/failing_task"
    And status_code 應為 500

  Scenario: Background task 成功時不寫入 error_events
    Given 一個正常完成的 async 追蹤任務
    When 透過 safe_background_task 執行該任務並追蹤錯誤
    Then write_error_event 不應被呼叫

  Scenario: 帶 tenant_id context 的 background task 錯誤
    Given 一個會拋出例外的 async 任務且帶有 tenant_id "T-001"
    When 透過 safe_background_task 執行該任務並追蹤錯誤
    Then write_error_event 應被呼叫一次
    And tenant_id 應為 "T-001"
