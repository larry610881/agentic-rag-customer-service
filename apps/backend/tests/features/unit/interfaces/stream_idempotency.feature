Feature: 串流的 Idempotency-Key 與 Last-Event-ID 重播（Issue #99 一-1）
  串流端點帶 key 時把整段事件快照存起來；同 key 重送不再打 LLM，
  從快照重播，並可用 Last-Event-ID 只補送缺漏的尾段。

  Scenario: 帶 key 第一次串流：事件全部送出且快照存入
    Given 一個記憶體快照 store 與串流 guard
    When 以 key "s1" 執行串流三個事件
    Then 收到 3 個 frame 且 producer 執行次數為 1
    And 快照 "idem:t1:client:c1:agent.chat.stream:s1" 含 3 個事件

  Scenario: 同 key 重送從快照重播且不執行 producer
    Given 一個記憶體快照 store 與串流 guard
    When 以 key "s1" 執行串流三個事件
    And 以 key "s1" 再執行串流
    Then 第二次收到與第一次相同的 3 個 frame
    And producer 執行次數為 1
    And 第二次 claim 標記為重播

  Scenario: Last-Event-ID 只補送缺漏的尾段
    Given 一個記憶體快照 store 與串流 guard
    When 以 key "s1" 執行串流三個事件
    And 以 key "s1" 與 Last-Event-ID 2 再執行串流
    Then 第二次只收到 seq 3 的 frame

  Scenario: 同 key 不同指紋拒絕
    Given 一個記憶體快照 store 與串流 guard
    When 以 key "s1" 執行串流三個事件
    And 以 key "s1" 但指紋 "other" 開始串流
    Then 回 ApiError 422 "idempotency_key_reused"

  Scenario: 同 key 處理中回衝突
    Given 一個記憶體快照 store 與串流 guard
    And 快照 store 中 "idem:t1:client:c1:agent.chat.stream:s1" 已是處理中且指紋 "fp"
    When 以 key "s1" 直接開始串流
    Then 回 ApiError 409 "idempotency_in_progress"

  Scenario: producer 中途拋例外時釋放 key
    Given 一個記憶體快照 store 與串流 guard
    And producer 會在第二個事件後拋例外
    When 以 key "s1" 執行串流三個事件
    Then 拋出 producer 的例外
    And 快照 store 中不存在 "idem:t1:client:c1:agent.chat.stream:s1"

  Scenario: 快照超過大小上限時不存，重送會真的重跑
    Given 一個記憶體快照 store 與上限 50 bytes 的串流 guard
    When 以 key "s1" 執行串流三個事件
    And 以 key "s1" 再執行串流
    Then producer 執行次數為 2

  Scenario: 不帶 key 時直接執行且無快照
    Given 一個記憶體快照 store 與串流 guard
    When 不帶 key 執行串流三個事件
    Then 收到 3 個 frame 且 producer 執行次數為 1
    And 快照 store 是空的

  Scenario Outline: Last-Event-ID 標頭解析
    When 解析 Last-Event-ID "<raw>"
    Then 解析結果為 <value>

    Examples:
      | raw   | value |
      | 7     | 7     |
      | abc   | none  |
      | -1    | none  |
