Feature: 租戶管理員 AI 對話完整體驗
  作為租戶管理員
  我希望能與 AI 客服對話
  以驗證對話系統正常運作（FakeLLM 模式，不驗證回覆品質）

  Scenario: 發送訊息並收到回覆
    Given 租戶管理員已登入
    And 使用者在對話頁面
    When 使用者發送訊息 "請問你們的保固政策是什麼？"
    Then 應顯示 Agent 回覆

  Scenario: 多輪對話驗證
    Given 租戶管理員已登入
    And 使用者在對話頁面
    When 使用者發送訊息 "我要退貨"
    Then 應顯示 Agent 回覆
    When 使用者發送訊息 "ORD-001"
    Then 應顯示 Agent 回覆
