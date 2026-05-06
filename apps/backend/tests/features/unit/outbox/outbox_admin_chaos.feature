Feature: Outbox Admin DLQ + 失敗注入（Phase E）
  作為平台管理員，我要能看到 DLQ 並對失敗事件重排或放棄
  也驗證連續失敗 → DLQ → admin retry → 後續 drain 成功的端到端循環

  Scenario: handler 連續失敗 N 次後事件進 DLQ
    Given outbox 有 1 筆 attempts=7 max_attempts=8 的 pending 事件
    And handler 對應 vector.delete 會拋 ConnectionError
    When drain worker 跑一次
    Then 該事件 status 應為 "dead"
    And outbox stats dead_count 應為 1

  Scenario: admin requeue 把 dead 事件變回 pending（attempts 歸零）
    Given outbox 有 1 筆 status=dead attempts=8 的事件
    When admin 對該事件 requeue
    Then 該事件 status 應為 "pending"
    And 該事件 attempts 應為 0
    And outbox stats dead_count 應為 0

  Scenario: admin abandon 把事件 hard-delete
    Given outbox 有 1 筆 status=dead attempts=8 的事件
    When admin 對該事件 abandon 並備註原因 "確認資料已不需要"
    Then 該事件應從 outbox 完全消失
    And outbox stats dead_count 應為 0

  Scenario: 完整失敗→DLQ→admin retry→drain 成功循環
    Given outbox 有 1 筆 attempts=7 max_attempts=8 的 pending 事件
    And handler 對應 vector.delete 會拋 ConnectionError
    When drain worker 跑一次
    Then 該事件 status 應為 "dead"
    Given handler 對應 vector.delete 改為會成功執行
    When admin 對該事件 requeue
    Then 該事件 status 應為 "pending"
    When drain worker 跑一次
    Then 該事件 status 應為 "done"
