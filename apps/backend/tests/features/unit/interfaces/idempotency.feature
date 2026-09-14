Feature: Idempotency-Key 重送保護（Issue #95）
  建立型 POST 帶 Idempotency-Key 時，同 key 同 body 在保留期內重送回同一份回應，
  handler 與記帳只執行一次；Redis 不可用時 fail-open。

  Scenario: 帶 key 第一次執行 handler 並寫入快照
    Given 一個記憶體快照 store 與 guard
    When 以 key "k1" 與 body 指紋 "fp-a" 執行 guard
    Then handler 執行次數為 1
    And 結果未標記為重播
    And store 中 "idem:t1:client:c1:agent.chat:k1" 的狀態為 "done" 且 TTL 為 86400

  Scenario: 同 key 同 body 重送直接回快照
    Given 一個記憶體快照 store 與 guard
    When 以 key "k1" 與 body 指紋 "fp-a" 執行 guard
    And 以 key "k1" 與 body 指紋 "fp-a" 執行 guard
    Then handler 執行次數為 1
    And 結果標記為重播
    And 兩次結果的 body 相同

  Scenario: 同 key 不同 body 拒絕
    Given 一個記憶體快照 store 與 guard
    When 以 key "k1" 與 body 指紋 "fp-a" 執行 guard
    And 以 key "k1" 與 body 指紋 "fp-b" 執行 guard
    Then 拋出 IdempotencyKeyReused
    And handler 執行次數為 1

  Scenario: 同 key 處理中回衝突
    Given 一個記憶體快照 store 與 guard
    And store 中 "idem:t1:client:c1:agent.chat:k1" 已是處理中且指紋 "fp-a"
    When 以 key "k1" 與 body 指紋 "fp-a" 執行 guard
    Then 拋出 IdempotencyInProgress
    And handler 執行次數為 0

  Scenario: handler 拋例外時釋放 key，重送真的重跑
    Given 一個記憶體快照 store 與 guard
    And handler 第一次會拋例外
    When 以 key "k1" 與 body 指紋 "fp-a" 執行 guard
    Then 拋出 handler 的例外
    And store 中不存在 "idem:t1:client:c1:agent.chat:k1"
    When 以 key "k1" 與 body 指紋 "fp-a" 執行 guard
    Then handler 執行次數為 2
    And 結果未標記為重播

  Scenario: handler 回非 2xx 時不快取
    Given 一個記憶體快照 store 與 guard
    And handler 會回狀態碼 403
    When 以 key "k1" 與 body 指紋 "fp-a" 執行 guard
    Then store 中不存在 "idem:t1:client:c1:agent.chat:k1"

  Scenario: store 不可用時照常執行且不拋錯
    Given 一個不可用的 store 與 guard
    When 以 key "k1" 與 body 指紋 "fp-a" 執行 guard
    And 以 key "k1" 與 body 指紋 "fp-a" 執行 guard
    Then handler 執行次數為 2
    And 結果未標記為重播

  Scenario: 不同主體同 key 互相隔離
    Given 一個記憶體快照 store 與 guard
    When 以 scope "t1:client:c1:agent.chat" key "k1" 指紋 "fp-a" 執行 guard
    And 以 scope "t2:client:c9:agent.chat" key "k1" 指紋 "fp-a" 執行 guard
    Then handler 執行次數為 2

  Scenario: 處理中標記的 TTL 比完成快照短
    Given 一個記憶體快照 store 與 guard
    And handler 會在執行中檢查 store
    When 以 key "k1" 與 body 指紋 "fp-a" 執行 guard
    Then handler 執行中看到的狀態為 "in_progress" 且 TTL 為 130

  Scenario Outline: 標頭格式檢查
    When 以標頭值 "<value>" 解析 Idempotency-Key
    Then 解析結果為 <outcome>

    Examples:
      | value                                | outcome |
      | 8f1c2d3e-aaaa-bbbb-cccc-111122223333 | ok      |
      | abc                                  | ok      |
      | (empty)                              | error   |
      | has space                            | error   |
      | (too-long)                           | error   |

  Scenario: 不帶標頭時 run_idempotent 直接呼叫 handler 並回原物件
    Given 一個記憶體快照 store 與 guard
    When 以無 key 呼叫 run_idempotent
    Then 回傳的是原始回應模型

  Scenario: 帶 key 時 run_idempotent 回 JSONResponse 並標記重播
    Given 一個記憶體快照 store 與 guard
    When 以 key "k9" 呼叫 run_idempotent 兩次
    Then 第一次回應標頭 Idempotent-Replayed 為 "false"
    And 第二次回應標頭 Idempotent-Replayed 為 "true"
    And 兩次回應 body 相同

  Scenario: run_idempotent 把處理中衝突轉成 409 並帶 Retry-After
    Given 一個記憶體快照 store 與 guard
    And store 中 "idem:t1:client:c1:agent.chat:k9" 已是處理中且指紋 "fp"
    When 以 key "k9" 呼叫 run_idempotent 一次
    Then 拋出 ApiError 狀態 409 code "idempotency_in_progress" 且 Retry-After 為 "1"

  Scenario: Redis store 的 claim 三種結果
    Given 一個以假 Redis 建立的 RedisIdempotencyStore
    When Redis SET NX 回成功
    Then claim 結果為 acquired
    When Redis SET NX 回失敗且 GET 回一筆 done 紀錄
    Then claim 結果為 existing 且狀態 "done"
    When Redis 拋出 RedisError
    Then claim 結果為 unavailable
