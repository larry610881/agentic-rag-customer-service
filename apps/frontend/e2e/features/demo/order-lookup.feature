Feature: Demo 3 — 訂單狀態查詢
  作為電商平台客戶
  我希望能夠查詢訂單狀態
  以便了解訂單的最新進度

  Background:
    Given 使用者已登入為 "Demo Store"
    And 使用者在對話頁面

  Scenario: 查詢訂單取得狀態資訊
    When 使用者發送訊息 "請問訂單 ORD-001 的狀態？"
    Then 應顯示 Agent 回覆
    And 回覆應包含訂單狀態資訊
    And 應顯示使用了 "order_lookup" 工具
