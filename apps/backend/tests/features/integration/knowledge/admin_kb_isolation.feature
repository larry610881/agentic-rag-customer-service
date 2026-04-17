Feature: 系統租戶 KB 隔離 (S-Gov.3)
  admin 在一般 endpoint 只看系統租戶自己的 KB，
  跨租戶視圖透過 /admin/knowledge-bases 取得，
  一般租戶呼叫 /admin/* 應 403

  Scenario: admin 呼叫 /knowledge-bases 只看到系統租戶的 KB
    Given 系統管理員已登入
    And 一般租戶 "client-a" 已建立 KB "客戶A的KB"
    When 系統管理員送出 GET /api/v1/knowledge-bases
    Then 回應狀態碼為 200
    And KB 列表不應包含 "客戶A的KB"

  Scenario: admin 呼叫 /admin/knowledge-bases 看到跨租戶
    Given 系統管理員已登入
    And 一般租戶 "client-b" 已建立 KB "客戶B的KB"
    When 系統管理員送出 GET /api/v1/admin/knowledge-bases
    Then 回應狀態碼為 200
    And KB 列表應包含 "客戶B的KB"

  Scenario: 一般租戶呼叫 /admin/knowledge-bases 應 403
    Given 一般租戶已登入
    When 一般租戶送出 GET /api/v1/admin/knowledge-bases
    Then 回應狀態碼為 403
