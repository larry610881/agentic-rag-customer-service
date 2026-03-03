Feature: Conversation API Integration
  使用真實 DB 驗證對話 CRUD API（含 JWT 認證 + 租戶隔離）

  Background:
    Given 已登入為租戶 "Conv Corp"

  Scenario: 空對話列表
    When 我送出認證 GET /api/v1/conversations
    Then 回應狀態碼為 200
    And 回應為空陣列

  Scenario: 查詢不存在的對話回傳 404
    When 我送出認證 GET /api/v1/conversations/00000000-0000-0000-0000-000000000000
    Then 回應狀態碼為 404

  Scenario: 未認證時拒絕存取
    When 我不帶 token 送出 GET /api/v1/conversations
    Then 回應狀態碼為 401

  Scenario: 租戶隔離 — 看不到其他租戶的對話
    Given 另一租戶 "Other Corp" 有對話記錄
    When 我送出認證 GET /api/v1/conversations
    Then 回應為空陣列
