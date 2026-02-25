Feature: Message Metadata Capture
  訊息回應中應包含延遲時間與檢索 chunk 資料

  Scenario: 回應訊息包含延遲時間
    Given 一個已設定好的 Agent Service
    When 使用者發送訊息 "查詢退貨政策"
    Then 助理訊息應包含 latency_ms 且為正整數

  Scenario: 回應訊息包含 retrieved_chunks
    Given 一個回傳來源引用的 Agent Service
    When 使用者發送訊息 "查詢退貨政策"
    Then 助理訊息應包含 retrieved_chunks 列表

  Scenario: 無來源時 retrieved_chunks 為 None
    Given 一個不回傳來源的 Agent Service
    When 使用者發送訊息 "你好"
    Then 助理訊息的 retrieved_chunks 應為 None
