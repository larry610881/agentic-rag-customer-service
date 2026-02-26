Feature: LINE Webhook 簽名驗證時序 (Signature Verification Timing)

  Scenario: 無效簽名搭配 malformed JSON 應先驗簽失敗
    Given Bot "bot-sec-001" 已設定 LINE Channel 且簽名驗證會失敗
    When 系統收到無效簽名且 body 為 malformed JSON 的 Webhook
    Then 應拋出簽名驗證失敗錯誤
    And 不應嘗試解析事件

  Scenario: 有效簽名搭配 malformed event 應 gracefully 處理
    Given Bot "bot-sec-002" 已設定 LINE Channel 且簽名驗證會通過
    When 系統收到有效簽名但 events 格式異常的 Webhook
    Then 不應拋出錯誤
    And 不應呼叫 Agent 處理訊息
