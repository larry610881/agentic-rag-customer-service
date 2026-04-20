Feature: Token Ledger 扣費 + 月度重置 — S-Token-Gov.2

  作為平台維運人員
  我希望使用者用 token 時自動扣本月 ledger
  以便每月可結算用量並支援自動續約 (Token-Gov.3)

  Background:
    Given admin 已登入並 seed 三個方案
    And 已建立租戶 "ledger-co" 綁定 plan "starter"

  Scenario: 第一次扣費 — 自動建本月 ledger
    When record_usage 寫入 1500 tokens (category=rag) 給 ledger-co
    Then 該租戶本月 ledger 應存在
    And base_remaining 應為 9998500
    And total_used_in_cycle 應為 1500

  Scenario: 連續扣費 — 累計扣 base
    When record_usage 寫入 1000 tokens 給 ledger-co
    And record_usage 寫入 500 tokens 給 ledger-co
    Then base_remaining 應為 9998500

  Scenario: base 用完 — addon 變負（軟上限）
    Given ledger-co 本月 ledger base_remaining=100 addon_remaining=0
    When record_usage 寫入 500 tokens 給 ledger-co
    Then base_remaining 應為 0
    And addon_remaining 應為 -400

  Scenario: 月度重置 — addon 從上月 carryover
    Given ledger-co 上月 ledger addon_remaining=2000
    When 執行 ProcessMonthlyResetUseCase
    Then 應為 ledger-co 建本月新 ledger
    And 本月 base_remaining 應等於 plan.base_monthly_tokens
    And 本月 addon_remaining 應為 2000

  Scenario: included_categories 過濾 — 只扣指定 category
    Given ledger-co 設定 included_categories=["rag"]
    When record_usage 寫入 1000 tokens (category=rag) 給 ledger-co
    And record_usage 寫入 500 tokens (category=embedding) 給 ledger-co
    Then base_remaining 應為 9999000
    And total_used_in_cycle 應為 1000
