Feature: Document Chunking
  文件分塊服務能將長文字切分為適當大小的 chunks

  Scenario: 短文件產生單一 chunk
    Given 一段 100 字元的短文字
    When 執行分塊處理
    Then 產生 1 個 chunk

  Scenario: 長文件產生多個 chunks
    Given 一段 1500 字元的長文字
    When 執行分塊處理
    Then 產生至少 3 個 chunks
    And 每個 chunk 不超過 500 字元

  Scenario: chunks 保留 document 和 tenant 關聯
    Given 一段 1500 字元的長文字
    When 以 document_id "doc-123" 和 tenant_id "tenant-456" 執行分塊
    Then 每個 chunk 的 document_id 為 "doc-123"
    And 每個 chunk 的 tenant_id 為 "tenant-456"
