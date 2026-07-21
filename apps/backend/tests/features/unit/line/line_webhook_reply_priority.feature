Feature: LINE Webhook 回覆優先於持久化
  使用者體感延遲以 LINE 回覆送達為終點，
  對話持久化、trace 寫入、token 記帳都應在回覆送出後才執行。

  Scenario: 回覆先於所有持久化動作送出
    Given 一個綁定 LINE Channel 且掛載對話儲存的 Bot
    And Agent 服務已準備好回覆內容
    When 系統處理一則 LINE 文字訊息事件
    Then LINE 回覆應在對話持久化之前送出

  Scenario: 載入動畫不阻塞主流程
    Given 一個綁定 LINE Channel 且掛載對話儲存的 Bot
    And Agent 服務已準備好回覆內容
    And LINE 載入動畫 API 需要 1 秒才回應
    When 系統處理一則 LINE 文字訊息事件
    Then 主流程不應等待載入動畫完成才開始處理

  Scenario: 回覆失敗時對話仍完成持久化
    Given 一個綁定 LINE Channel 且掛載對話儲存的 Bot
    And Agent 服務已準備好回覆內容
    And LINE 回覆 API 會拋出例外
    When 系統處理一則 LINE 文字訊息事件並容忍回覆失敗
    Then 對話仍應被持久化
