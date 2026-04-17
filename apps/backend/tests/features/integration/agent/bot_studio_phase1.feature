Feature: Bot Studio Phase 1 — 真實對應的命脈
  Stream events 帶 node_id 對應 trace.nodes、worker_routing event 讓前端知道選哪個 worker、
  失敗路徑寫入 outcome=failed 節點、既有通路無破壞。

  Scenario: Stream 事件帶 node_id 應對應到 trace 的某筆節點
    Given 一般租戶已登入
    And 該租戶已建立一個 bot
    When 我送出 POST /api/v1/agent/chat/stream 帶 identity_source "studio"
    Then SSE done 事件應包含 trace_id 欄位
    And SSE 事件中至少一筆帶 node_id 應對應到 DB trace 的 nodes[]

  Scenario: 多 worker bot 送訊息時 SSE 應收到 worker_routing event
    Given 一般租戶已登入
    And 該租戶已建立一個 bot 且綁定 2 個 worker "售前" 與 "售後"
    When 我送出 POST /api/v1/agent/chat/stream 帶 identity_source "studio" 訊息 "我想退貨"
    Then SSE 事件序列應包含一筆 type 為 "worker_routing" 的事件
    And 該事件應含 worker_name 欄位

  Scenario: Agent 失敗應在 trace 寫入 outcome failed 節點
    Given 一般租戶已登入
    And 該租戶已建立一個 bot
    When agent 執行過程中發生錯誤後送出 POST /api/v1/agent/chat/stream
    Then DB 中該 trace 應有至少一筆 outcome 為 "failed" 的節點
    And 該節點 metadata 應含 error_message 欄位

  Scenario: 既有 web 通路不帶 identity_source 應無破壞
    Given 一般租戶已登入
    And 該租戶已建立一個 bot
    When 我送出 POST /api/v1/agent/chat/stream 不帶 identity_source
    Then SSE done 事件應包含 trace_id 欄位
    And DB 中該 trace_id 對應的 trace.source 應為 "web"
    And DB 中該 trace 所有節點的 outcome 應為 "success"
