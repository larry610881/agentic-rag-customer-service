Feature: JSON Record-Based Chunking
  JSON 資料以物件為單位分塊，保持記錄完整性

  Scenario: JSON array of objects 按物件邊界分塊
    Given 一段包含 5 筆記錄的 JSON array 且 chunk_size 為 200
    When 執行 JSON 分塊處理
    Then 每個 chunk 都包含完整的記錄（不會斷在欄位中間）

  Scenario: 多筆小記錄合併到同一 chunk 不超過 chunk_size
    Given 一段包含 3 筆小記錄的 JSON array 且 chunk_size 為 2000
    When 執行 JSON 分塊處理
    Then 產生 1 個 JSON chunk
    And 該 chunk 包含全部 3 筆記錄

  Scenario: 單筆超大 record 獨立成一個 chunk
    Given 一段包含 1 筆超大記錄的 JSON array 且 chunk_size 為 50
    When 執行 JSON 分塊處理
    Then 產生 1 個 JSON chunk
    And 該 chunk 的 metadata 包含 record_start 和 record_end

  Scenario: 巢狀 object 中找到 array 進行分塊
    Given 一段包含巢狀 array 的 JSON object 且 chunk_size 為 200
    When 執行 JSON 分塊處理
    Then 每個 chunk 都包含完整的記錄（不會斷在欄位中間）

  Scenario: 非 array JSON fallback 到遞迴分塊
    Given 一段不含 array 的 JSON object
    When 執行 JSON 分塊處理
    Then 使用 fallback splitter 處理
