Feature: LINE 回饋收集 (LINE Feedback Collection)

  Scenario: 使用者透過 Postback 提交正面回饋
    Given LINE Bot 收到一則 postback 事件，data 為 "feedback:msg-abc:thumbs_up"
    When 系統處理該 postback 事件
    Then 應建立一筆 rating 為 "thumbs_up" 的回饋
    And 回饋的 channel 應為 "line"

  Scenario: 使用者透過 Postback 提交負面回饋
    Given LINE Bot 收到一則 postback 事件，data 為 "feedback:msg-abc:thumbs_down"
    When 系統處理該 postback 事件
    Then 應建立一筆 rating 為 "thumbs_down" 的回饋

  Scenario: 無效的 Postback data 格式應忽略
    Given LINE Bot 收到一則 postback 事件，data 為 "invalid_data"
    When 系統處理該 postback 事件
    Then 應忽略該事件且不建立回饋
