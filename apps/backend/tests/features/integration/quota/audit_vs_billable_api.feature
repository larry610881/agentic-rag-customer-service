Feature: Admin quota overview 審計 vs 計費 並列顯示 (S-Ledger-Unification)

  作為平台系統管理員
  我希望在 /admin/quota-overview 看到審計總量與計費總量並列
  以便判斷平台吸收了多少免費 tokens

  Background:
    Given admin 已登入並 seed 三個方案
    And 已建立租戶 "audit-bill-co" 綁定 plan "starter"

  Scenario: 全部計入 — audit 與 billable 皆相等
    Given audit-bill-co 的 included_categories 為 null
    And audit-bill-co 本月寫入 usage 1000 tokens category "llm"
    And audit-bill-co 本月寫入 usage 500 tokens category "embedding"
    When admin 呼叫 GET /api/v1/admin/tenants/quotas
    Then 租戶 "audit-bill-co" 的 total_audit_in_cycle 應為 1500
    And 租戶 "audit-bill-co" 的 total_billable_in_cycle 應為 1500

  Scenario: 只計入 llm — billable 小於 audit 代表平台吸收
    Given audit-bill-co 的 included_categories 為 ["llm"]
    And audit-bill-co 本月寫入 usage 800 tokens category "llm"
    And audit-bill-co 本月寫入 usage 400 tokens category "embedding"
    When admin 呼叫 GET /api/v1/admin/tenants/quotas
    Then 租戶 "audit-bill-co" 的 total_audit_in_cycle 應為 1200
    And 租戶 "audit-bill-co" 的 total_billable_in_cycle 應為 800

  Scenario: 租戶視角 /quota 只看 billable
    Given audit-bill-co 的 included_categories 為 ["llm"]
    And audit-bill-co 本月寫入 usage 2000 tokens category "llm"
    And audit-bill-co 本月寫入 usage 500 tokens category "embedding"
    When 租戶 audit-bill-co 呼叫 GET /api/v1/tenants/{id}/quota
    Then 回應 total_billable_in_cycle 應為 2000
    And 回應不應包含 total_audit_in_cycle 欄位

  Scenario: base_total 減 base_remaining 永遠等於 billable（不允許任何 drift）
    Given audit-bill-co 的 included_categories 為 null
    And audit-bill-co 本月寫入 usage 1234567 tokens category "llm"
    When 租戶 audit-bill-co 呼叫 GET /api/v1/tenants/{id}/quota
    Then base_total 減 base_remaining 應等於 total_billable_in_cycle
