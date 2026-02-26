Feature: CSV Chunking
  CSV 資料以行為單位分塊，保持記錄完整性

  Scenario: CSV 資料以行為單位分塊且不切斷記錄
    Given 一段包含 header 和 10 行資料的 CSV 文字且 chunk_size 為 200
    When 執行 CSV 分塊處理
    Then 每個 chunk 中的資料行都是完整的一行

  Scenario: 每個 chunk 包含 header 保留欄位名稱上下文
    Given 一段包含 header 和 10 行資料的 CSV 文字且 chunk_size 為 200
    When 執行 CSV 分塊處理
    Then 每個 chunk 的第一行都是 header

  Scenario: 單行超過 chunk_size 時獨立為一個 chunk
    Given 一段包含 header 和一行超長資料的 CSV 文字且 chunk_size 為 50
    When 執行 CSV 分塊處理
    Then 產生 1 個 CSV chunk
    And 該 chunk 包含 header 和該超長行

  Scenario: 空 CSV 回傳空列表
    Given 一段只有 header 的 CSV 文字
    When 執行 CSV 分塊處理
    Then 產生 0 個 CSV chunk
