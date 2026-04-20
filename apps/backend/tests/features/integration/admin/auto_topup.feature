Feature: 自動續約 + 額度警示 — S-Token-Gov.3

  作為平台維運人員
  我希望租戶 addon 餘額為負時系統自動補一個 pack 並寫入交易紀錄
  以便客戶服務不中斷、月底有完整對帳依據

  Background:
    Given admin 已登入並 seed 三個方案
    And 已建立租戶 "topup-co" 綁定 plan "starter"

  Scenario: 第一次扣到 addon ≤ 0 — 自動續約 + 寫 BillingTransaction
    Given topup-co 本月 ledger base_remaining=0 addon_remaining=500
    When record_usage 寫入 1500 tokens 給 topup-co
    Then addon_remaining 應為 4999000
    And 該租戶本月應有 1 筆 BillingTransaction
    And 最新 BillingTransaction.transaction_type 應為 "auto_topup"
    And 最新 BillingTransaction.addon_tokens_added 應為 5000000

  Scenario: 連續扣費觸發 2 次 topup
    Given topup-co 本月 ledger base_remaining=0 addon_remaining=500
    When record_usage 寫入 1500 tokens 給 topup-co
    And record_usage 寫入 5000000 tokens 給 topup-co
    Then 該租戶本月應有 2 筆 BillingTransaction
    And addon_remaining 應為 4999000

  Scenario: POC plan (addon_pack_tokens=0) 不續約
    Given 已建立 plan "no_topup" 其 addon_pack_tokens=0
    And 已建立租戶 "frugal-co" 綁定 plan "no_topup"
    And frugal-co 本月 ledger base_remaining=0 addon_remaining=500
    When record_usage 寫入 1500 tokens 給 frugal-co
    Then addon_remaining 應為 -1000
    And 該租戶本月應有 0 筆 BillingTransaction

  Scenario: ProcessQuotaAlertsUseCase 寫 80% / 100% 警示且重跑冪等
    Given topup-co 本月 ledger base_remaining=2000000 addon_remaining=5000000
    When 執行 ProcessQuotaAlertsUseCase
    Then topup-co 應有 1 筆 base_warning_80 警示
    And topup-co 應有 0 筆 base_exhausted_100 警示
    When 再執行一次 ProcessQuotaAlertsUseCase
    Then topup-co 應有 1 筆 base_warning_80 警示
    Given topup-co 本月 ledger base_remaining=0 addon_remaining=4000000
    When 執行 ProcessQuotaAlertsUseCase
    Then topup-co 應有 1 筆 base_warning_80 警示
    And topup-co 應有 1 筆 base_exhausted_100 警示
