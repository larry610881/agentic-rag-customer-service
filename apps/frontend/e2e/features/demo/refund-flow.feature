Feature: Demo 4 — 退貨多步驟流程
  作為電商平台客戶
  我希望能夠透過 AI 客服完成退貨申請
  以便快速處理退貨需求

  Background:
    Given 使用者已登入為 "Demo Store"
    And 使用者在對話頁面

  Scenario: 三步驟退貨引導
    When 使用者發送訊息 "我要退貨"
    Then 應顯示 Agent 回覆
    And 回覆應要求提供訂單編號
    When 使用者發送訊息 "ORD-001"
    Then 應顯示 Agent 回覆
    And 回覆應確認訂單並詢問退貨原因
    When 使用者發送訊息 "商品有瑕疵"
    Then 應顯示 Agent 回覆
    And 回覆應包含工單編號
