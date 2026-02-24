Feature: Demo 6 — LINE Bot 對話 → Agent 回答
  作為 LINE Bot 整合系統
  我需要接收 LINE Webhook 並透過 Agent 回覆
  以便驗證 LINE Bot 端到端 Mock 流程

  Background:
    Given LINE Channel Secret 為 "test-secret-key"
    And Agent 服務使用 Fake 模式

  Scenario: LINE 用戶傳送知識型問題，Agent 回覆知識庫答案
    Given LINE 用戶 "U001" 傳送訊息 "你們的保固政策是什麼？"
    When 系統收到帶有效簽名的 Webhook 請求
    Then HTTP 回應狀態碼為 200
    And Agent 應處理訊息 "你們的保固政策是什麼？"
    And LINE 應回覆包含 "保固" 的答案

  Scenario: LINE 用戶傳送訂單查詢，Agent 使用 OrderLookup 工具
    Given LINE 用戶 "U002" 傳送訊息 "我的訂單 ORD-001 目前狀態？"
    When 系統收到帶有效簽名的 Webhook 請求
    Then HTTP 回應狀態碼為 200
    And Agent 應處理訊息 "我的訂單 ORD-001 目前狀態？"
    And LINE 應回覆包含 "訂單" 的答案

  Scenario: LINE 用戶傳送退貨請求，Agent 啟動退貨流程
    Given LINE 用戶 "U003" 傳送訊息 "我要退貨"
    When 系統收到帶有效簽名的 Webhook 請求
    Then HTTP 回應狀態碼為 200
    And Agent 應處理訊息 "我要退貨"
    And LINE 應回覆包含 "退貨" 的答案

  Scenario: 無效簽名的 Webhook 請求被拒絕
    Given LINE 用戶 "U004" 傳送訊息 "任意訊息"
    When 系統收到帶無效簽名的 Webhook 請求
    Then HTTP 回應狀態碼為 403
    And Agent 不應被呼叫
    And LINE 不應回覆任何訊息

  Scenario: 非文字訊息事件被忽略
    Given LINE 用戶 "U005" 傳送了圖片訊息
    When 系統收到帶有效簽名的 Webhook 請求
    Then HTTP 回應狀態碼為 200
    And Agent 不應被呼叫
    And LINE 不應回覆任何訊息
