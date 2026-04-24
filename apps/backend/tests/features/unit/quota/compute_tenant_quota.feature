Feature: 統一配額計算 — ComputeTenantQuotaUseCase (S-Ledger-Unification)

  作為平台系統設計者
  我希望所有 quota 欄位都從 token_usage_records 即時算出
  讓 base_total - base_remaining 與 billable 總量結構上永遠相等

  Background:
    Given 已建立租戶 "acme" 綁定 plan "starter" base_total=10000000

  Scenario: 全部計入 — audit 與 billable 完全相等
    Given 租戶 "acme" 的 included_categories 為 null
    And 租戶 "acme" 本月寫入 usage 800000 tokens category "llm"
    And 租戶 "acme" 本月寫入 usage 200000 tokens category "embedding"
    When 呼叫 ComputeTenantQuotaUseCase 查詢 "acme"
    Then total_audit_in_cycle 應等於 1000000
    And total_billable_in_cycle 應等於 1000000
    And base_remaining 應等於 9000000
    And base_total 減 base_remaining 應等於 total_billable_in_cycle

  Scenario: 只計入 llm — billable 小於 audit 但 base 扣量等於 billable
    Given 租戶 "acme" 的 included_categories 為 ["llm"]
    And 租戶 "acme" 本月寫入 usage 800000 tokens category "llm"
    And 租戶 "acme" 本月寫入 usage 200000 tokens category "embedding"
    When 呼叫 ComputeTenantQuotaUseCase 查詢 "acme"
    Then total_audit_in_cycle 應等於 1000000
    And total_billable_in_cycle 應等於 800000
    And base_remaining 應等於 9200000
    And base_total 減 base_remaining 應等於 total_billable_in_cycle

  Scenario: 全部不計入 — base 不被扣任何
    Given 租戶 "acme" 的 included_categories 為 []
    And 租戶 "acme" 本月寫入 usage 500000 tokens category "llm"
    When 呼叫 ComputeTenantQuotaUseCase 查詢 "acme"
    Then total_audit_in_cycle 應等於 500000
    And total_billable_in_cycle 應等於 0
    And base_remaining 應等於 10000000

  Scenario: 超額進 addon — overage 從 topup 池扣
    Given 租戶 "acme" 的 included_categories 為 null
    And 租戶 "acme" 已有 topup 紀錄 2000000
    And 租戶 "acme" 本月寫入 usage 11500000 tokens category "llm"
    When 呼叫 ComputeTenantQuotaUseCase 查詢 "acme"
    Then base_remaining 應等於 0
    And addon_remaining 應等於 500000

  Scenario: 超額超過 addon — addon 為負（軟上限）
    Given 租戶 "acme" 的 included_categories 為 null
    And 租戶 "acme" 已有 topup 紀錄 1000000
    And 租戶 "acme" 本月寫入 usage 12000000 tokens category "llm"
    When 呼叫 ComputeTenantQuotaUseCase 查詢 "acme"
    Then base_remaining 應等於 0
    And addon_remaining 應等於 -1000000

  Scenario: 規則變更追溯生效 — 改 included_categories 後下次查詢就套新規則
    Given 租戶 "acme" 的 included_categories 為 null
    And 租戶 "acme" 本月寫入 usage 700000 tokens category "llm"
    And 租戶 "acme" 本月寫入 usage 300000 tokens category "embedding"
    When 呼叫 ComputeTenantQuotaUseCase 查詢 "acme"
    Then total_billable_in_cycle 應等於 1000000
    When 更新租戶 "acme" 的 included_categories 為 ["llm"]
    And 呼叫 ComputeTenantQuotaUseCase 查詢 "acme"
    Then total_billable_in_cycle 應等於 700000
    And base_remaining 應等於 9300000
