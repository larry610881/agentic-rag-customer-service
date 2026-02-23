Feature: Conversation Memory
  Agent 支援多輪對話記憶

  Scenario: 多輪對話載入歷史
    Given 租戶 "tenant-001" 已有一個對話
    And 對話中已有使用者訊息 "你好"
    When 使用者在同一對話發送 "退貨政策是什麼"
    Then Agent 回應應包含 "根據先前對話"

  Scenario: conversation_id 跨請求一致
    Given 租戶 "tenant-001" 發送第一條訊息 "你好"
    When 使用者用相同 conversation_id 發送第二條訊息 "謝謝"
    Then 兩次回應的 conversation_id 應一致

  Scenario: 新對話不含歷史
    Given 租戶 "tenant-001" 未建立對話
    When 使用者發送新對話訊息 "你好"
    Then Agent 回應不應包含 "根據先前對話"
