Feature: Observability API 權限守衛（S-Gov.3）
  作為系統
  我要求所有 observability GET 端點都必須認證
  非 admin 只能看自己租戶的資料
  admin 可指定 tenant_id 跨租戶查詢，未指定則看全部租戶（觀測場景需要全域視野）

  Scenario: 未帶 token 呼叫 observability 端點回 401
    When 我不帶 token 呼叫 GET /api/v1/observability/agent-traces
    Then 回應狀態碼為 401

  Scenario: 一般租戶呼叫時只能看自己租戶的 traces
    Given 一般租戶 "tenant-a" 已登入
    And 租戶 "tenant-a" 有 1 筆 agent trace
    And 租戶 "tenant-b" 有 1 筆 agent trace
    When 租戶 "tenant-a" 呼叫 GET /api/v1/observability/agent-traces 不帶 tenant_id
    Then 回應中只包含 tenant-a 的 trace

  Scenario: admin 可指定其他租戶查詢 traces
    Given admin 已登入
    And 租戶 "tenant-a" 有 1 筆 agent trace
    When admin 呼叫 GET /api/v1/observability/agent-traces 帶 tenant_id "tenant-a"
    Then 回應中包含 tenant-a 的 trace

  Scenario: admin 不帶 tenant_id 時看全部租戶 traces
    Given admin 已登入
    And SYSTEM 租戶有 0 筆 agent trace
    And 租戶 "tenant-a" 有 1 筆 agent trace
    When admin 呼叫 GET /api/v1/observability/agent-traces 不帶 tenant_id
    Then 回應中包含 tenant-a 的 trace
