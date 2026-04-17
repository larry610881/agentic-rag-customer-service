Feature: Admin 一般功能 API 租戶過濾（S-Gov.3）
  作為系統管理員
  我的身份是 SYSTEM_TENANT_ID 租戶
  即使帶 bot_id 參數呼叫一般功能 API
  也不應越權看到 / 操作其他租戶的資料
  跨租戶行為一律走系統管理區專用 API

  Scenario: admin 列出對話時只回傳 SYSTEM 租戶對話
    Given admin 已登入
    And 系統租戶有 1 個對話 "sys-conv-1"
    And 租戶 "tenant-a" 有 1 個對話 "a-conv-1"
    When admin 呼叫 GET /api/v1/conversations 不帶 bot_id
    Then 結果應只包含 "sys-conv-1"

  Scenario: admin 帶其他租戶 bot_id 查詢對話時不越權
    Given admin 已登入
    And 租戶 "tenant-a" 有 bot "bot-a" 與對話 "a-conv-1"
    When admin 呼叫 GET /api/v1/conversations 帶 bot_id "bot-a"
    Then 結果應為空

  Scenario: admin 發訊息時 tenant_id 永遠是 SYSTEM_TENANT_ID
    Given admin 已登入
    And 租戶 "tenant-a" 有 bot "bot-a"
    When admin 呼叫 POST /api/v1/agent/chat 帶 bot_id "bot-a"
    Then SendMessageCommand 的 tenant_id 應為 SYSTEM_TENANT_ID

  Scenario: admin 送 feedback 時 tenant_id 永遠是 SYSTEM_TENANT_ID
    Given admin 已登入
    And 租戶 "tenant-a" 有對話 "a-conv-1"
    When admin 呼叫 POST /api/v1/feedback 指向 conversation "a-conv-1"
    Then SubmitFeedbackCommand 的 tenant_id 應為 SYSTEM_TENANT_ID
