Feature: LINE Webhook Bot 路由
  作為 LINE Bot 系統
  我需要根據端點路徑決定使用預設設定或 Bot 設定
  以便同時支援舊端點和新多租戶端點

  Scenario: 新端點接收帶 Bot ID 的 Webhook 並呼叫 execute_for_bot
    Given Bot "bot-route-001" 已設定且返回有效 LINE 服務
    When 系統收到發往 "/api/v1/webhook/line/bot-route-001" 的 Webhook
    Then 應呼叫 execute_for_bot 並傳入 Bot ID "bot-route-001"

  Scenario: 舊端點仍使用預設設定呼叫 execute
    Given 系統有預設 LINE 服務設定
    When 系統收到發往 "/api/v1/webhook/line" 的舊端點 Webhook
    Then 應呼叫 execute 並使用預設設定
