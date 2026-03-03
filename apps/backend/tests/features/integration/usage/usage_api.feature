Feature: Usage API Integration
  使用真實 DB 驗證 Token 用量查詢 API

  Background:
    Given 已登入為租戶 "Usage Corp"

  Scenario: 空用量查詢
    When 我送出認證 GET /api/v1/usage
    Then 回應狀態碼為 200
    And 用量 total_tokens 為 0

  Scenario: 有用量紀錄時查詢統計
    Given 已有用量紀錄
    When 我送出認證 GET /api/v1/usage
    Then 回應狀態碼為 200
    And 用量 total_tokens 大於 0

  Scenario: 未認證時拒絕存取
    When 我不帶 token 送出 GET /api/v1/usage
    Then 回應狀態碼為 401
