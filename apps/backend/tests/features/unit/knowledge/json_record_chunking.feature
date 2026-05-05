Feature: JSON Record-Based Chunking
  JSON 資料以物件邊界分塊：每筆 record 永遠是 1 個 chunk，不依 chunk_size
  合併小記錄。理由：JSON 隔壁的 record 不一定相關（例如 FAQ 中「藥局」
  跟「輪胎中心」），合併會稀釋 embedding 信號 → 搜尋命中率下降。

  Scenario: JSON array of objects 一筆 record 對應一個 chunk
    Given 一段包含 5 筆記錄的 JSON array 且 chunk_size 為 200
    When 執行 JSON 分塊處理
    Then 產生 5 個 JSON chunk
    And 每個 chunk 都包含完整的記錄（不會斷在欄位中間）

  Scenario: 多筆小記錄不再合併到同一 chunk（避免主題稀釋）
    Given 一段包含 3 筆小記錄的 JSON array 且 chunk_size 為 2000
    When 執行 JSON 分塊處理
    Then 產生 3 個 JSON chunk

  Scenario: 單筆超大 record 仍獨立成一個 chunk
    Given 一段包含 1 筆超大記錄的 JSON array 且 chunk_size 為 50
    When 執行 JSON 分塊處理
    Then 產生 1 個 JSON chunk
    And 該 chunk 的 metadata 包含 record_start 和 record_end

  Scenario: 巢狀 object 中找到 array 進行分塊（每筆 record 各自 1 chunk）
    Given 一段包含巢狀 array 的 JSON object 且 chunk_size 為 200
    When 執行 JSON 分塊處理
    Then 產生 3 個 JSON chunk
    And 每個 chunk 都包含完整的記錄（不會斷在欄位中間）

  Scenario: 非 array JSON fallback 到遞迴分塊
    Given 一段不含 array 的 JSON object
    When 執行 JSON 分塊處理
    Then 使用 fallback splitter 處理
