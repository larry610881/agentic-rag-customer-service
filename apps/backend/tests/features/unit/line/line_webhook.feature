Feature: LINE Bot Webhook 處理
  作為 LINE Bot 系統
  我需要接收並處理 LINE Webhook 事件
  以便透過 Agent 回覆用戶訊息

  Scenario: 接收文字訊息並回覆 Agent 答案
    Given LINE 用戶 "U1234567890" 發送了文字訊息 "我想查詢退貨政策"
    And Agent 服務回覆 "根據退貨政策，您可以在30天內退貨。"
    When 系統處理 LINE Webhook 事件
    Then 系統應透過 LINE API 回覆 "根據退貨政策，您可以在30天內退貨。"

  Scenario: 驗證 LINE Webhook 簽名
    Given 一個帶有有效簽名的 Webhook 請求
    When 系統驗證簽名
    Then 驗證應通過

  Scenario: 拒絕無效簽名的 Webhook 請求
    Given 一個帶有無效簽名的 Webhook 請求
    When 系統驗證簽名
    Then 驗證應失敗

  Scenario: 忽略非文字訊息事件
    Given LINE 用戶發送了一個圖片訊息事件
    And Agent 服務已準備就緒
    When 系統處理 LINE Webhook 事件
    Then 系統不應呼叫 Agent 服務
    And 系統不應透過 LINE API 回覆

  Scenario: Agent 回答包含工具調用資訊
    Given LINE 用戶 "U9876543210" 發送了文字訊息 "我的訂單 ORD-001 狀態如何？"
    And Agent 服務回覆 "您的訂單 ORD-001 正在配送中。" 並包含工具調用 "order_lookup"
    When 系統處理 LINE Webhook 事件
    Then 系統應透過 LINE API 回覆 "您的訂單 ORD-001 正在配送中。"
