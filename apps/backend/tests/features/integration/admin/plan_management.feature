Feature: Plan Template CRUD + 租戶綁 plan — S-Token-Gov.1

  作為 system_admin
  我希望管理「方案」並把租戶綁到方案
  以便後續 ledger / 計費系統有基準參數可讀

  Background:
    Given admin 已登入並 seed 三個方案

  Scenario: List plans 應回傳已 seed 的方案
    When admin 列出所有方案
    Then 應回 200
    And 列表應包含 "poc" "starter" "pro" 三個方案

  Scenario: Create plan 成功
    When admin 建立方案 "enterprise" base=50000000 base_price=15000
    Then 應回 201
    And 回傳的 plan name 應為 "enterprise"

  Scenario: Create plan 重複名稱回 409
    When admin 建立方案 "starter" base=10000000 base_price=3000
    Then 應回 409

  Scenario: Update plan 改 base_monthly_tokens
    When admin 編輯方案 "starter" 設 base_monthly_tokens=20000000
    Then 應回 200
    And base_monthly_tokens 應為 20000000

  Scenario: Soft delete plan
    When admin 刪除方案 "starter" force=false
    Then 應回 204
    And 該 plan is_active 應為 false

  Scenario: Assign plan 給租戶
    Given 已建立租戶 "test-corp"
    When admin 將 "pro" 指派給 "test-corp"
    Then 應回 204
    And tenant 的 plan 應為 "pro"

  Scenario: 一般租戶無法 list plans
    Given 已建立並登入租戶 "user-co"
    When user-co 嘗試列出所有方案
    Then 應回 403
