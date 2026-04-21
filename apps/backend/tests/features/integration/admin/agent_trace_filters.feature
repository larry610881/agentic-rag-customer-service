Feature: Agent Trace 多維 Filter + Conversation 聚合 — S-Gov.6a

  作為平台系統管理員
  我希望以多維度條件查詢 agent trace
  以便快速找到要 debug 的 trace 或回顧整段對話

  Background:
    Given admin 已登入
    And 已建立租戶 "trace-co"
    And 已建立租戶 "trace-co" 的 bot "trace-bot"

  Scenario: 多維 filter 組合 — source + outcome
    Given 已 seed 4 筆 trace：
      | name   | source | outcome | total_ms |
      | t1     | line   | failed  | 1500     |
      | t2     | line   | success | 800      |
      | t3     | web    | failed  | 2000     |
      | t4     | widget | success | 500      |
    When admin 呼叫 GET /api/v1/observability/agent-traces?source=line&outcome=failed
    Then 回應應包含 1 筆 trace
    And 該筆 trace 名稱為 "t1"

  Scenario: 耗時範圍 filter
    Given 已 seed 3 筆 trace：
      | name | total_ms |
      | r1   | 500      |
      | r2   | 2000     |
      | r3   | 5000     |
    When admin 呼叫 GET /api/v1/observability/agent-traces?min_total_ms=1000&max_total_ms=3000
    Then 回應應包含 1 筆 trace
    And 該筆 trace 名稱為 "r2"

  Scenario: Keyword 搜尋 nodes 內容
    Given 已 seed 3 筆 trace 內含不同 user_input：
      | name | input_keyword |
      | k1   | 我要退貨        |
      | k2   | 訂單查詢        |
      | k3   | 我要退貨流程    |
    When admin 呼叫 GET /api/v1/observability/agent-traces?keyword=退貨
    Then 回應應包含 2 筆 trace
    And 結果應包含 "k1" 與 "k3"

  Scenario: Conversation 聚合視圖
    # 排序：按該 group 最近 trace 時間 desc — 後 seed 的 group 排第一
    Given 已 seed 同一 conversation 3 筆 trace
    And 已 seed 另一 conversation 2 筆 trace
    When admin 呼叫 GET /api/v1/observability/agent-traces?group_by_conversation=true
    Then 回應應為 grouped 結構含 2 個 group
    And 第一 group 的 trace_count 應為 2
    And 第二 group 的 trace_count 應為 3
