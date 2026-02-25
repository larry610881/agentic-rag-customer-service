Feature: Feedback Export
  回饋資料匯出支援 CSV/JSON 格式和 PII 遮蔽

  Scenario: 匯出 JSON 格式回饋
    Given 租戶 "t-001" 有可匯出的回饋資料
    When 以 JSON 格式匯出（不遮蔽 PII）
    Then 回傳內容應為合法 JSON 且包含回饋記錄

  Scenario: 匯出 CSV 格式回饋
    Given 租戶 "t-001" 有可匯出的回饋資料
    When 以 CSV 格式匯出（不遮蔽 PII）
    Then 回傳內容應為合法 CSV 含標題列

  Scenario: 匯出時啟用 PII 遮蔽
    Given 租戶 "t-001" 有含 PII 的回饋資料
    When 以 JSON 格式匯出（啟用 PII 遮蔽）
    Then user_id 應被遮蔽

  Scenario: 無資料時匯出空結果
    Given 租戶 "t-002" 無回饋資料
    When 以 JSON 格式匯出（不遮蔽 PII）
    Then 回傳空 JSON 陣列
