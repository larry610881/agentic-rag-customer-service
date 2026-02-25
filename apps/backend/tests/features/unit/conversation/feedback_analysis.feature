Feature: Feedback Analysis APIs
  回饋分析 API 提供趨勢、根因、檢索品質和 Token 成本統計

  Scenario: 查詢滿意度趨勢
    Given 租戶 "t-001" 有 30 天內的回饋資料
    When 查詢滿意度趨勢（30 天）
    Then 應回傳每日統計列表含 positive 和 negative

  Scenario: 查詢差評根因 Top Issues
    Given 租戶 "t-001" 有含 tags 的差評資料
    When 查詢差評根因（30 天，top 10）
    Then 應回傳 tag 計數列表且依 count 降序

  Scenario: 查詢檢索品質記錄
    Given 租戶 "t-001" 有差評和對應的訊息上下文
    When 查詢檢索品質（30 天）
    Then 應回傳包含使用者問題和助理回答的記錄

  Scenario: 查詢 Token 成本統計
    Given 租戶 "t-001" 有使用記錄
    When 查詢 Token 成本統計（30 天）
    Then 應回傳每模型的 token 和成本摘要

  Scenario: 無資料時回傳空列表
    Given 租戶 "t-002" 無任何回饋資料
    When 查詢滿意度趨勢（30 天）
    Then 應回傳空列表
