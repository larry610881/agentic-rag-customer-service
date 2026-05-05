Feature: Outbox Pattern — publish + drain
  作為架構師，我要 PG ↔ Milvus 雙寫達到 eventual consistency
  業務 use case 在 PG transaction 內 INSERT outbox row + 業務 SQL（atomic）
  async drain worker 撈出來對 vector store 套用，失敗自動 backoff，達 max attempts 進 DLQ

  Scenario: publish 把事件寫進 outbox（不 commit，由 caller 控制）
    Given 一個空的 outbox repository
    When 應用層 publish 一個 vector.delete 事件
    Then outbox repository 應收到一筆 status="pending" 的事件
    And 事件的 attempts 應為 0

  Scenario: drain 撈到事件並成功處理
    Given outbox 有 1 筆 vector.delete pending 事件
    And handler 對應 vector.delete 會成功執行
    When drain worker 跑一次
    Then 該事件 status 應為 "done"
    And handler 應被呼叫 1 次

  Scenario: drain 失敗時走 backoff retry
    Given outbox 有 1 筆 vector.delete pending 事件
    And handler 對應 vector.delete 會拋 ConnectionError
    When drain worker 跑一次
    Then 該事件 attempts 應為 1
    And 該事件 status 應為 "pending"
    And 該事件 next_attempt_at 應晚於現在

  Scenario: drain 連續失敗達 max_attempts 進 DLQ
    Given outbox 有 1 筆 attempts=7 max_attempts=8 的 pending 事件
    And handler 對應 vector.delete 會拋 ConnectionError
    When drain worker 跑一次
    Then 該事件 status 應為 "dead"
    And 該事件 attempts 應為 8

  Scenario: 未註冊的 event_type 直接進 dead 避免無限重試
    Given outbox 有 1 筆 event_type="vector.unknown_xyz" 的 pending 事件
    And handler registry 不含該 event_type
    When drain worker 跑一次
    Then 該事件 status 應為 "dead"
