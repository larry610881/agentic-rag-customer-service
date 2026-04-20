Feature: 收益儀表板 — S-Token-Gov.4

  作為平台系統管理員
  我希望從 BillingTransaction 聚合查看月營收 / plan 分布 / top 租戶
  以便快速掌握平台的 SaaS KPI

  Background:
    Given admin 已登入並 seed 三個方案
    And 已建立租戶 "alpha-co" 綁定 plan "starter"
    And 已建立租戶 "beta-co" 綁定 plan "pro"

  Scenario: 聚合正確 — monthly_revenue + by_plan + top_tenants
    Given alpha-co 在 cycle "2026-03" 有 1 筆 auto_topup 金額 1500 TWD addon 5000000
    And alpha-co 在 cycle "2026-04" 有 2 筆 auto_topup 金額 1500 TWD addon 5000000
    And beta-co 在 cycle "2026-04" 有 1 筆 auto_topup 金額 3500 TWD addon 15000000
    When admin 呼叫 GET /api/v1/admin/billing/dashboard
    Then 回應 monthly_revenue 應有 2 筆
    And 回應 by_plan 應有 2 筆
    And 回應 top_tenants 第 1 名應為 "alpha-co" 累計營收 4500
    And 回應 top_tenants 第 2 名應為 "beta-co" 累計營收 3500
    And 回應 total_revenue 應為 8000
    And 回應 total_transactions 應為 4

  Scenario: cycle range filter — 只查指定月份
    Given alpha-co 在 cycle "2026-03" 有 1 筆 auto_topup 金額 1500 TWD addon 5000000
    And alpha-co 在 cycle "2026-04" 有 2 筆 auto_topup 金額 1500 TWD addon 5000000
    When admin 呼叫 GET /api/v1/admin/billing/dashboard?start=2026-04&end=2026-04
    Then 回應 monthly_revenue 應有 1 筆
    And 回應 total_revenue 應為 3000
    And 回應 total_transactions 應為 2

  Scenario: 非 admin 訪問儀表板 — 拒絕 403
    Given 已建立非 admin 使用者 "regular-user" 綁定 alpha-co
    When regular-user 呼叫 GET /api/v1/admin/billing/dashboard
    Then 回應狀態碼應為 403
