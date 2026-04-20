Feature: 額度警示 Email 寄送 — S-Token-Gov.3.5

  作為平台維運人員
  我希望系統自動把 quota_alert_logs 內未寄的警示透過 SendGrid 寄給租戶 admin
  以便客戶在額度吃緊時能即時收到通知

  Background:
    Given admin 已登入並 seed 三個方案
    And 已建立租戶 "email-co" 綁定 plan "starter"
    And email-co 有一筆未寄的 base_warning_80 警示

  Scenario: 正常寄送 + 標 delivered
    Given email-co 有一位 admin 使用者 email "admin@email-co.com"
    When 執行 QuotaEmailDispatchUseCase
    Then mock SendGrid 應被呼叫 1 次
    And 收件者應為 "admin@email-co.com"
    And 該警示 delivered_to_email 應為 True

  Scenario: 無 admin email — 跳過寄送但仍標 delivered（避免無限重試）
    When 執行 QuotaEmailDispatchUseCase
    Then mock SendGrid 應被呼叫 0 次
    And 該警示 delivered_to_email 應為 True

  Scenario: 寄送失敗 — 不標 delivered（下次 cron 重試）
    Given email-co 有一位 admin 使用者 email "fail@email-co.com"
    And mock SendGrid 設定為失敗
    When 執行 QuotaEmailDispatchUseCase
    Then mock SendGrid 應被呼叫 1 次
    And 該警示 delivered_to_email 應為 False
