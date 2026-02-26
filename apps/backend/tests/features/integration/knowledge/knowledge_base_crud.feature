Feature: Knowledge Base CRUD Integration
  使用真實 DB 驗證知識庫 CRUD API（含 JWT 認證 + 租戶隔離）

  Scenario: 成功建立知識庫
    Given 已登入為租戶 "Alpha Corp"
    When 我送出認證 POST /api/v1/knowledge-bases 名稱為 "FAQ"
    Then 回應狀態碼為 201
    And 回應包含 name 為 "FAQ" 且含 tenant_id

  Scenario: 未認證時拒絕存取
    When 我不帶 token 送出 POST /api/v1/knowledge-bases 名稱為 "FAQ"
    Then 回應狀態碼為 401

  Scenario: 查詢自己的知識庫列表
    Given 已登入為租戶 "Alpha Corp"
    And 該租戶有知識庫 "FAQ"
    And 該租戶有知識庫 "政策"
    When 我送出認證 GET /api/v1/knowledge-bases
    Then 回應狀態碼為 200
    And 回應包含 2 個知識庫

  Scenario: 租戶隔離 — 看不到其他租戶的知識庫
    Given 租戶 "Alpha" 有知識庫 "Alpha FAQ"
    And 租戶 "Beta" 有知識庫 "Beta FAQ"
    When 我以 "Alpha" 身分查詢知識庫列表
    Then 回應只包含 "Alpha FAQ"

  Scenario: 無效 JWT token 回傳 401
    When 我帶無效 token 送出 GET /api/v1/knowledge-bases
    Then 回應狀態碼為 401
