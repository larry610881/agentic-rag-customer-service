Feature: LINE Feedback Reason Follow-up
  使用者按下 thumbs_down 後追問原因，解析 feedback_reason postback

  Scenario: thumbs_down 後發送追問原因選項
    Given 一個 LINE 使用者按下 thumbs_down
    When 系統處理該 postback 事件
    Then 應儲存 thumbs_down 回饋
    And 應呼叫 reply_with_reason_options

  Scenario: 使用者選擇追問原因 tag
    Given 一個已回饋 thumbs_down 的訊息 "msg-001"
    When 使用者選擇原因 "incorrect"
    Then 該回饋的 tags 應包含 "incorrect"
    And 應回覆確認訊息

  Scenario: thumbs_up 回覆感謝
    Given 一個 LINE 使用者按下 thumbs_up
    When 系統處理該 postback 事件
    Then 應儲存 thumbs_up 回饋
    And 應回覆感謝訊息
