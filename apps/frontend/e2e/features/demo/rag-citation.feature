Feature: Demo 2 — RAG 知識問答與來源引用
  作為電商平台客戶
  我希望查詢知識庫時能看到引用來源
  以便確認回覆的可信度

  Background:
    Given 使用者已登入為 "Demo Store"
    And 使用者在對話頁面

  Scenario: 知識型問題顯示引用來源
    When 使用者發送訊息 "請問退貨流程是什麼？"
    Then 應顯示 Agent 回覆
    And 回覆應包含 "退貨" 相關內容
    And 應顯示引用來源區域
