Feature: Agent Scenarios
  Agent 端對端場景能正確處理各類用戶請求

  Scenario: 用戶查詢訂單狀態得到包含狀態的完整回答
    Given Agent 服務已準備好處理訂單查詢
    When 用戶查詢 "我的訂單 ORD-001 狀態如何"
    Then 回答應包含訂單狀態資訊

  Scenario: 用戶查詢退貨政策走 RAG 回答附帶來源
    Given Agent 服務已準備好處理知識查詢
    When 用戶查詢 "退貨政策是什麼"
    Then 回答應包含知識庫內容
    And 回答應附帶來源引用

  Scenario: 用戶投訴後成功建立工單
    Given Agent 服務已準備好處理投訴
    When 用戶發送 "我要投訴，商品有問題"
    Then 回答應確認工單已建立
