Feature: RAG 知識問答 (RAG Query)
  作為電商平台客戶
  我希望能夠透過 AI 客服查詢知識庫內容
  以便快速得到準確的產品與服務資訊

  Background:
    Given 使用者已登入為 "Demo Store"
    And 使用者在對話頁面

  Scenario: 發送問題並收到 AI 回覆
    When 使用者輸入訊息 "請問退貨流程是什麼？"
    And 使用者點擊送出按鈕
    Then 應顯示 AI 回覆
