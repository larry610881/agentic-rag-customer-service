Feature: Tenant CRUD Integration
  使用真實 DB 驗證租戶 CRUD API 完整流程

  Scenario: 成功建立租戶
    When 我送出 POST /api/v1/tenants 名稱為 "Alpha Corp"
    Then 回應狀態碼為 201
    And 回應包含 name 為 "Alpha Corp" 且 plan 為 "starter"

  Scenario: 重複名稱建立租戶回傳 409
    Given 已存在租戶 "Alpha Corp"
    When 我送出 POST /api/v1/tenants 名稱為 "Alpha Corp"
    Then 回應狀態碼為 409

  Scenario: 查詢租戶列表
    Given 已存在租戶 "Alpha Corp"
    And 已存在租戶 "Beta Inc"
    When 我送出 GET /api/v1/tenants
    Then 回應狀態碼為 200
    And 回應包含 2 個租戶

  Scenario: 查詢單一租戶
    Given 已存在租戶 "Alpha Corp"
    When 我用該租戶 ID 送出 GET /api/v1/tenants/{id}
    Then 回應狀態碼為 200
    And 回應的 name 為 "Alpha Corp"

  Scenario: 查詢不存在的租戶回傳 404
    When 我送出 GET /api/v1/tenants/non-existent-id
    Then 回應狀態碼為 404
