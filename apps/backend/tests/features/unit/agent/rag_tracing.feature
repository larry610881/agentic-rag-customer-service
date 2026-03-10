Feature: RAG 查詢追蹤
  作為系統，我需要追蹤每次 RAG 查詢的完整鏈路以支援可觀測性

  Scenario: 完整追蹤鏈路記錄
    Given 一個 RAG 追蹤器已初始化
    When 開始一次 RAG 查詢追蹤 "退貨政策" 租戶 "T001"
    And 記錄 embed 步驟耗時 50ms
    And 記錄 retrieve 步驟耗時 120ms 取得 3 個 chunks
    And 完成追蹤總耗時 200ms
    Then 追蹤記錄應包含 2 個步驟
    And 追蹤記錄總耗時應為 200ms
    And 追蹤記錄 chunk_count 應為 3

  Scenario: 追蹤無結果的查詢
    Given 一個 RAG 追蹤器已初始化
    When 開始一次 RAG 查詢追蹤 "不存在的問題" 租戶 "T001"
    And 記錄 retrieve 步驟耗時 80ms 取得 0 個 chunks
    And 完成追蹤總耗時 100ms
    Then 追蹤記錄應包含 1 個步驟
    And 追蹤記錄 chunk_count 應為 0

  Scenario: 追蹤記錄包含 prompt snapshot
    Given 一個含有 system prompt 的追蹤記錄
    When 序列化為 dict
    Then 應包含 prompt_snapshot 欄位且值為該 system prompt

  Scenario: Flush 清空並回傳所有記錄
    Given 一個 RAG 追蹤器已初始化
    And 已完成 2 筆追蹤記錄
    When 執行 flush
    Then 應回傳 2 筆追蹤記錄
    And 追蹤 buffer 應為空
