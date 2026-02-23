Feature: Conversation History
  支援查詢對話列表與單一對話

  Scenario: 查詢租戶對話列表
    Given 租戶 "tenant-001" 有 2 個對話
    When 查詢租戶 "tenant-001" 的對話列表
    Then 應回傳 2 個對話

  Scenario: 查詢單一對話詳情
    Given 一個已存在的對話含 3 條訊息
    When 查詢該對話的詳情
    Then 應回傳該對話含 3 條訊息
