Feature: Admin Tools API 整合測試
  系統管理員可透過 /admin/tools 管理 built-in tool 的 scope 與白名單
  一般租戶無權呼叫 admin 端點

  Scenario: 系統管理員可更新工具 scope 為 tenant 並設白名單
    Given 系統管理員已登入
    And 系統已 seed built-in tool "query_dm_with_image"
    When 我送出 PUT /api/v1/admin/tools/query_dm_with_image 設 scope 為 "tenant" 白名單為 "tenant-a"
    Then 回應狀態碼為 200
    And 回應中 scope 為 "tenant"
    And 回應中 tenant_ids 包含 "tenant-a"

  Scenario: 一般租戶呼叫 admin 端點回 403
    Given 一般租戶已登入
    When 我送出 GET /api/v1/admin/tools
    Then 回應狀態碼為 403

  Scenario: GET /agent/built-in-tools 依租戶自動過濾
    Given 系統已 seed built-in tool "query_dm_with_image" 且 scope 為 "tenant" 白名單為 "tenant-a"
    And 系統已 seed built-in tool "rag_query" 且 scope 為 "global"
    And 租戶 "tenant-b" 已登入
    When 我送出 GET /api/v1/agent/built-in-tools
    Then 回應狀態碼為 200
    And 回應不應包含 "query_dm_with_image"
    And 回應應包含 "rag_query"
