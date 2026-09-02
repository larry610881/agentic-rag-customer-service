Feature: LINE Webhook 事件去重 (Webhook Event Deduplication)
  作為 LINE Bot 系統
  我需要以 webhookEventId 去重 LINE redelivery 重送的事件
  以便網路中斷或冷啟動逾時導致重送時不重複呼叫 LLM 與重複寫入

  Background:
    Given Bot "shop-a" 屬於租戶 "tenant-abc" 且設定了 LINE Channel 與去重器

  Scenario: 同一 webhookEventId 重送只處理一次
    Given Webhook body 含事件 "evt-001" 文字 "退貨政策"
    When 系統兩次以相同 body 執行 prepare_and_reply
    Then 第一次 context 應含 1 個文字事件
    And 第二次 context 應含 0 個文字事件

  Scenario: 不同 webhookEventId 各自處理
    Given Webhook body 含事件 "evt-001" 文字 "退貨政策"
    And 另一個 Webhook body 含事件 "evt-002" 文字 "門市在哪"
    When 系統依序以兩個 body 執行 prepare_and_reply
    Then 兩次 context 都應含 1 個文字事件

  Scenario: 無 webhookEventId 的事件不去重
    Given Webhook body 含未帶 webhookEventId 的文字事件 "舊格式"
    When 系統兩次以相同 body 執行 prepare_and_reply
    Then 兩次 context 都應含 1 個文字事件
    And 去重器不應被呼叫

  Scenario: postback 事件同樣去重
    Given Webhook body 含 postback 事件 "evt-pb-001" 資料 "action=like"
    When 系統兩次以相同 body 執行 prepare_and_reply
    Then 第一次 context 應含 1 個 postback 事件
    And 第二次 context 應含 0 個 postback 事件

  Scenario: 重送事件解析時標記 is_redelivery
    Given Webhook body 含事件 "evt-001" 文字 "退貨政策" 且 deliveryContext.isRedelivery 為 true
    When 系統以該 body 執行 prepare_and_reply
    Then 第一次 context 的文字事件 is_redelivery 應為 true

  Scenario: 重送時 Agent 只被呼叫一次
    Given Webhook body 含事件 "evt-001" 文字 "退貨政策"
    And Agent 服務已準備回覆 "30 天內可退貨"
    When 系統兩次以相同 body 執行 execute_for_bot
    Then Agent 服務應只被呼叫 1 次

  Scenario: 舊端點 execute 也去重
    Given 舊端點文字事件 "evt-legacy-001" 文字 "退貨政策"
    And Agent 服務已準備回覆 "30 天內可退貨"
    When 系統兩次以相同事件列表執行 execute
    Then Agent 服務應只被呼叫 1 次

  Scenario: 未注入去重器時行為不變
    Given Bot "shop-a" 屬於租戶 "tenant-abc" 且設定了 LINE Channel 但未注入去重器
    And Webhook body 含事件 "evt-001" 文字 "退貨政策"
    When 系統兩次以相同 body 執行 prepare_and_reply
    Then 兩次 context 都應含 1 個文字事件

  # ── Redis 實作 ──

  Scenario: Redis 去重器以 SET NX EX 認領事件
    Given Redis SET NX 回傳成功
    When 去重器認領事件 "evt-001"
    Then 認領結果應為 true
    And 應以 key "line:evt:evt-001" 與 TTL 3600 秒執行 SET NX

  Scenario: Redis 去重器對已存在的事件回傳 false
    Given Redis SET NX 回傳 None
    When 去重器認領事件 "evt-001"
    Then 認領結果應為 false

  Scenario: Redis 不可用時去重器 fail-open
    Given Redis SET 拋出例外
    When 去重器認領事件 "evt-001"
    Then 認領結果應為 true
