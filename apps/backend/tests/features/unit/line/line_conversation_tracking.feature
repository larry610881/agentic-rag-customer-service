Feature: LINE Webhook 對話追蹤
  LINE 用戶的訊息應走 conversation 系統，超時自動分段

  Scenario: LINE 用戶第一次發訊息應建立新 conversation
    Given 一個 LINE 用戶 "U001" 對 bot "bot-001" 發送第一條訊息
    And 該用戶沒有任何 conversation
    When webhook 處理該訊息
    Then 應建立新的 conversation
    And conversation 的 bot_id 應為 "bot-001"

  Scenario: 30 分鐘內的後續訊息應延續同一 conversation
    Given 一個 LINE 用戶 "U001" 已有 conversation "conv-001" 且最後訊息在 10 分鐘前
    When webhook 處理新訊息
    Then 應複用 conversation "conv-001"

  Scenario: 超過 30 分鐘應建立新 conversation
    Given 一個 LINE 用戶 "U001" 已有 conversation "conv-old" 且最後訊息在 40 分鐘前
    When webhook 處理新訊息
    Then 應建立新的 conversation
    And 新 conversation 的 id 不應為 "conv-old"

  Scenario: LINE 回饋應正確關聯 conversation_id
    Given 一個 message "msg-001" 屬於 conversation "conv-001"
    When LINE 用戶對 "msg-001" 給了 thumbs_up 回饋
    Then feedback 的 conversation_id 應為 "conv-001"
