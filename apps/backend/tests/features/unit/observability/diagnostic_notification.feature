Feature: Diagnostic notification dispatch

  Scenario: 診斷告警發送到已啟用診斷的管道
    Given 有一個已啟用且訂閱診斷告警的通知管道
    And 有一個 critical 級別的診斷事件
    When 執行診斷通知派發
    Then 通知應成功發送到該管道

  Scenario: 未啟用診斷告警的管道不會收到通知
    Given 有一個已啟用但未訂閱診斷告警的通知管道
    And 有一個 critical 級別的診斷事件
    When 執行診斷通知派發
    Then 通知不應發送

  Scenario: severity 過濾 — 管道設定 critical 時不收 warning
    Given 有一個已啟用且診斷嚴重度設為 critical 的管道
    And 有一個 warning 級別的診斷事件
    When 執行診斷通知派發
    Then 通知不應發送

  Scenario: severity 過濾 — 管道設定 warning 時收 warning
    Given 有一個已啟用且診斷嚴重度設為 warning 的管道
    And 有一個 warning 級別的診斷事件
    When 執行診斷通知派發
    Then 通知應成功發送到該管道

  Scenario: 錯誤通知管道設定 min_severity=off 時不收錯誤通知
    Given 有一個已啟用但 min_severity 設為 off 的通知管道
    And 有一個錯誤事件
    When 執行錯誤通知派發
    Then 通知不應發送
