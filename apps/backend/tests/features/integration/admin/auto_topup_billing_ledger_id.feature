Feature: auto_topup 寫入 BillingTransaction.ledger_id 指向真實 ledger (T1.1)

  作為平台金流審計人員
  我希望 auto_topup 觸發後 billing_transactions 正確記錄並指向 ledger
  以便每筆自動續約都有可追蹤的帳務依據，不會被 FK violation 靜默吞掉

  Background:
    Given admin 已登入並 seed 三個方案
    And 已建立租戶 "fk-co" 綁定 plan "starter"

  Scenario: auto_topup 觸發後 billing_transactions.ledger_id 指向真實 ledger
    Given fk-co 本月 base 和 addon 都已耗盡
    When record_usage 寫入 1000 tokens 給 fk-co
    Then fk-co 本月應有 1 筆 BillingTransaction
    And 最新 BillingTransaction.ledger_id 應等於 fk-co 本月 ledger.id

  Scenario: BillingTransaction.ledger_id 絕不應為空字串（FK regression guard）
    Given fk-co 本月 base 和 addon 都已耗盡
    When record_usage 寫入 1000 tokens 給 fk-co
    Then fk-co 本月應有 1 筆 BillingTransaction
    And 最新 BillingTransaction.ledger_id 不應為空字串
