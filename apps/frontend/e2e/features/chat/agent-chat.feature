Feature: AI Agent 對話 (Agent Chat)
  作為電商平台客戶
  我希望能夠與 AI Agent 對話
  以便獲得智能化的客服協助

  Background:
    Given 使用者已登入為 "Demo Store"
    And 使用者在對話頁面

  Scenario: 發送訊息並收到 Agent 回覆
    When 使用者輸入訊息 "你好，我想了解退貨政策"
    And 使用者點擊送出按鈕
    Then 應顯示 AI 正在處理的指示
    And 應顯示 Agent 回覆

  Scenario: Streaming 逐字回答
    When 使用者輸入訊息 "請介紹你們的服務"
    And 使用者點擊送出按鈕
    Then 回覆應以串流方式逐步顯示
    And 最終應顯示完整的 Agent 回覆
