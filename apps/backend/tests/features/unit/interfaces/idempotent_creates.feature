Feature: 建立型端點的 Idempotency-Key（Issue #98 步驟 7）
  會計費或會產生重複資料的建立型端點重用 IdempotencyGuard：
  同 key 同 body 重送回同一份 201 回應並標記重播，下游只執行一次。

  Scenario: 五支建立型端點都宣告 Idempotency-Key 依賴
    When 檢查五支建立型端點的簽名
    Then 每一支都有 idempotency_key 與 idempotency_guard 參數

  Scenario: submit_feedback 同 key 重送回同一份 201 且 use case 只執行一次
    Given 一個記憶體快照 guard 與回傳固定回饋的 SubmitFeedback use case
    When 以 key "fb-1" 連續呼叫 submit_feedback 兩次
    Then 兩次狀態碼皆為 201
    And 第二次標頭 Idempotent-Replayed 為 "true" 且 body 與第一次相同
    And SubmitFeedback use case 執行次數為 1

  Scenario: create_api_key 不帶 key 時行為不變
    Given 一個記憶體快照 guard 與回傳固定金鑰的 CreateApiKey use case
    When 不帶 key 呼叫 create_api_key
    Then 回傳的是 ApiKeyCreatedResponse 模型

  Scenario: run_idempotent 可指定 201 狀態碼
    Given 一個記憶體快照 guard
    When 以 status_code 201 與 key "k-201" 呼叫 run_idempotent
    Then 回應狀態碼為 201 且標頭 Idempotent-Replayed 為 "false"
