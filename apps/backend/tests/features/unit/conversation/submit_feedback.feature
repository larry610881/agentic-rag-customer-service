Feature: 提交回饋 (Submit Feedback)

  Scenario: 成功提交正面回饋
    Given 租戶 "tenant-1" 有一段對話 "conv-1" 包含 assistant 訊息 "msg-1"
    When 我對訊息 "msg-1" 提交 "thumbs_up" 回饋，通路為 "web"
    Then 回饋應成功建立
    And 回饋的 rating 應為 "thumbs_up"

  Scenario: 成功提交負面回饋附帶評論
    Given 租戶 "tenant-1" 有一段對話 "conv-1" 包含 assistant 訊息 "msg-1"
    When 我對訊息 "msg-1" 提交 "thumbs_down" 回饋，評論為 "答案不正確"
    Then 回饋應成功建立
    And 回饋的 comment 應為 "答案不正確"

  Scenario: 重複回饋同一訊息應失敗
    Given 訊息 "msg-1" 已有一筆回饋
    When 我對訊息 "msg-1" 再次提交回饋
    Then 應拋出重複實體錯誤

  Scenario: 對不存在的對話提交回饋應失敗
    Given 租戶 "tenant-1" 沒有對話 "conv-unknown"
    When 我對對話 "conv-unknown" 的訊息 "msg-1" 提交回饋
    Then 應拋出實體未找到錯誤
