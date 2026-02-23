Feature: AI Agent 對話 (Agent Chat)
  作為電商平台客戶
  我希望能夠與 AI Agent 對話
  以便獲得智能化的客服協助

  Background:
    Given 使用者已登入為 "demo@example.com"
    And 使用者在對話頁面

  Scenario: Agent 查詢訂單
    When 使用者輸入訊息 "幫我查詢訂單 ORD-20240101 的狀態"
    And 使用者點擊送出按鈕
    Then 應顯示 AI 正在處理的指示
    And 應顯示 Agent 回覆
    And 回覆應包含訂單狀態資訊

  Scenario: Agent 退貨多步驟引導
    When 使用者輸入訊息 "我想退貨，訂單編號是 ORD-20240101"
    And 使用者點擊送出按鈕
    Then 應顯示 Agent 回覆
    And 回覆應包含退貨流程說明
    When 使用者輸入訊息 "確認退貨"
    And 使用者點擊送出按鈕
    Then 應顯示 Agent 回覆
    And 回覆應包含退貨確認資訊

  Scenario: Streaming 逐字回答
    When 使用者輸入訊息 "請介紹你們的熱銷商品"
    And 使用者點擊送出按鈕
    Then 應顯示 AI 正在處理的指示
    And 回覆應以串流方式逐步顯示
    And 最終應顯示完整的 Agent 回覆

  Scenario: 展開思考過程面板
    When 使用者輸入訊息 "幫我比較 A 方案和 B 方案的差異"
    And 使用者點擊送出按鈕
    Then 應顯示 Agent 回覆
    And 回覆應顯示思考過程摺疊區塊
    When 使用者點擊思考過程展開按鈕
    Then 應顯示思考過程詳情
    And 思考過程應包含工具調用記錄
