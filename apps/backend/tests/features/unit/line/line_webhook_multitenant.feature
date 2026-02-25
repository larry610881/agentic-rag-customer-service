Feature: LINE Webhook 多租戶處理
  作為多租戶 LINE Bot 系統
  我需要根據 Bot ID 路由 Webhook 到正確的租戶
  以便每個 Bot 使用獨立的 LINE 設定和知識庫

  Scenario: 透過 Bot ID 路由到正確租戶
    Given Bot "bot-001" 屬於租戶 "tenant-abc" 且設定了 LINE Channel
    And Agent 服務已準備回覆 "您好，歡迎使用！"
    When 系統透過 Bot ID "bot-001" 處理 Webhook 事件
    Then Agent 應使用租戶 "tenant-abc" 處理訊息
    And 系統應透過 Bot 的 LINE 服務回覆 "您好，歡迎使用！"

  Scenario: Bot 未設定 LINE Channel 時拒絕處理
    Given Bot "bot-002" 屬於租戶 "tenant-abc" 但未設定 LINE Channel
    When 系統透過 Bot ID "bot-002" 處理 Webhook 事件
    Then 應拋出 LINE Channel 未設定的錯誤

  Scenario: Bot ID 不存在時回傳錯誤
    Given Bot "bot-999" 不存在於系統中
    When 系統透過 Bot ID "bot-999" 處理 Webhook 事件
    Then 應拋出 Bot 不存在的錯誤

  Scenario: 使用 Bot 的 Channel Secret 驗簽
    Given Bot "bot-003" 設定了 Channel Secret "secret-xyz"
    And Webhook 請求帶有正確的簽名
    When 系統透過 Bot ID "bot-003" 處理 Webhook 事件
    Then 簽名驗證應使用 Bot 的 Channel Secret

  Scenario: 使用 Bot 的知識庫和系統提示呼叫 Agent
    Given Bot "bot-004" 屬於租戶 "tenant-def" 且設定了知識庫 "kb-a,kb-b" 和系統提示 "你是客服助手"
    And Agent 服務已準備回覆 "這是回答"
    When 系統透過 Bot ID "bot-004" 處理 Webhook 事件
    Then Agent 應使用知識庫 "kb-a,kb-b" 處理訊息
    And Agent 應使用系統提示 "你是客服助手" 處理訊息
