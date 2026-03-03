Feature: Chunk Deduplication
  分塊去重，移除完全相同內容的 chunks

  Scenario: 完全相同內容去重
    Given 一組包含重複內容的 chunks
    When 執行 chunk 去重
    Then 重複的 chunks 應被移除

  Scenario: 空白差異視為重複
    Given 一組內容相同但空白不同的 chunks
    When 執行 chunk 去重
    Then 空白差異的 chunks 應被視為重複並移除

  Scenario: 不同內容全部保留
    Given 一組內容各不相同的 chunks
    When 執行 chunk 去重
    Then 所有 chunks 應被保留
