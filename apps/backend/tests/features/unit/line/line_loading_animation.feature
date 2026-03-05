Feature: LINE Bot Loading Animation
  作為 LINE Bot 系統
  我需要在處理用戶訊息時顯示載入動畫
  以便用戶在等待 AI 回覆期間有視覺回饋

  Scenario: 預設端點處理訊息時觸發載入動畫
    Given 載入動畫測試用戶 "U-loading-001" 發送了文字訊息 "查詢訂單狀態"
    And 載入動畫測試 Agent 服務已準備回覆
    When 系統透過預設端點處理載入動畫 Webhook 事件
    Then 系統應對用戶 "U-loading-001" 顯示載入動畫
    And Agent 服務應被呼叫處理訊息

  Scenario: Bot 端點處理訊息時觸發載入動畫
    Given 載入動畫測試 Bot "shop-bot" 已設定 LINE Channel
    And 載入動畫測試 Agent 服務已準備回覆
    And 載入動畫測試用戶 "U-loading-002" 透過 Bot 發送了文字訊息 "查詢退貨政策"
    When 系統透過 Bot 端點處理載入動畫 Webhook 事件
    Then 系統應對用戶 "U-loading-002" 顯示載入動畫
    And Agent 服務應被呼叫處理訊息
