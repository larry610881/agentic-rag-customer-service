Feature: 系統租戶 Bot 隔離 (S-Gov.3)
  admin 在一般 endpoint 只看系統租戶自己的 Bot，
  跨租戶視圖透過 /admin/bots 取得，
  一般租戶呼叫 /admin/* 應 403

  Scenario: admin 呼叫 /bots 只看到系統租戶的 Bot
    Given 系統管理員已登入
    And 一般租戶 "client-c" 已建立 Bot "客戶C的Bot"
    When 系統管理員送出 GET /api/v1/bots
    Then 回應狀態碼為 200
    And Bot 列表不應包含 "客戶C的Bot"

  Scenario: admin 呼叫 /admin/bots 看到跨租戶
    Given 系統管理員已登入
    And 一般租戶 "client-d" 已建立 Bot "客戶D的Bot"
    When 系統管理員送出 GET /api/v1/admin/bots
    Then 回應狀態碼為 200
    And Bot 列表應包含 "客戶D的Bot"

  Scenario: 一般租戶呼叫 /admin/bots 應 403
    Given 一般租戶已登入
    When 一般租戶送出 GET /api/v1/admin/bots
    Then 回應狀態碼為 403
