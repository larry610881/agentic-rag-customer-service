Feature: 系統層額度總覽 — S-Token-Gov.2.5

  作為平台系統管理員
  我希望一次看到所有租戶當月 Token 額度狀況
  以便快速判斷誰快超用、誰閒置、是否該手動續約

  Background:
    Given admin 已登入並 seed 三個方案
    And 已建立租戶 "quota-alpha" 綁定 plan "starter"
    And 已建立租戶 "quota-beta" 綁定 plan "pro"
    And 已建立租戶 "quota-gamma" 綁定 plan "starter"

  Scenario: system_admin 列出當月所有租戶額度 — 含已啟用與未啟用
    Given quota-alpha 已寫入 1000 tokens 用量
    And quota-beta 已寫入 5000 tokens 用量
    When admin 呼叫 GET /api/v1/admin/tenants/quotas
    Then 回應應包含 3 筆租戶資料
    And 租戶 "quota-alpha" 的 has_ledger 應為 True
    And 租戶 "quota-alpha" 的 total_used_in_cycle 應為 1000
    And 租戶 "quota-beta" 的 has_ledger 應為 True
    And 租戶 "quota-beta" 的 total_used_in_cycle 應為 5000
    And 租戶 "quota-gamma" 的 has_ledger 應為 False
    And 租戶 "quota-gamma" 的 total_used_in_cycle 應為 0
    And 租戶 "quota-gamma" 的 base_total 應等於 plan.base_monthly_tokens

  Scenario: 指定 cycle 查歷史月份 — 該月無 ledger 顯示 0
    When admin 呼叫 GET /api/v1/admin/tenants/quotas?cycle=2025-01
    Then 回應應包含 3 筆租戶資料
    And 所有租戶的 has_ledger 應為 False
    And 所有租戶的 total_used_in_cycle 應為 0

  Scenario: 非 admin 訪問 quota 總覽 — 拒絕 403
    Given 已建立非 admin 使用者 "regular-user" 綁定 quota-alpha
    When regular-user 呼叫 GET /api/v1/admin/tenants/quotas
    Then 回應狀態碼應為 403
