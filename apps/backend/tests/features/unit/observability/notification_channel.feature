Feature: Notification Channel Management
  通知渠道管理 — CRUD、測試、多渠道發送

  Scenario: 建立 email 通知渠道（config 加密存儲）
    Given 管理員提供 email 渠道設定
    When 建立 email 通知渠道
    Then 渠道應建立成功
    And config 應被加密存儲

  Scenario: 啟用通知時新錯誤觸發寄信
    Given 一個已啟用的 email 通知渠道
    When 新錯誤事件發生並觸發通知分派
    Then 應呼叫 email sender 發送通知

  Scenario: Throttle 時間內不重複寄信
    Given 一個已啟用的 email 通知渠道且 throttle 為 15 分鐘
    And 同一 fingerprint 在 10 分鐘前已發送過通知
    When 同一 fingerprint 的新錯誤觸發通知分派
    Then 不應呼叫 email sender

  Scenario: 發送測試通知
    Given 一個已建立的 email 通知渠道
    When 管理員觸發測試通知
    Then 應呼叫 email sender 發送測試郵件

  Scenario: 多個 channel 都 enabled 時全部發送
    Given 兩個已啟用的通知渠道（email 和 slack）
    When 新錯誤事件觸發通知分派
    Then 兩個 sender 都應被呼叫
