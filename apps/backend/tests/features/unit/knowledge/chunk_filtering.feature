Feature: Chunk Filtering
  分塊品質過濾，移除過短或純雜訊的 chunks

  Scenario: 過濾過短 chunk
    Given 一組包含過短內容的 chunks
    When 執行 chunk 過濾
    Then 過短的 chunks 應被拒絕
    And 拒絕原因應為 "too_short"

  Scenario: 過濾純符號 chunk
    Given 一組包含純符號內容的 chunks
    When 執行 chunk 過濾
    Then 純符號的 chunks 應被拒絕
    And 拒絕原因應為 "noise_only"

  Scenario: 正常 chunk 保留
    Given 一組正常品質的 chunks 待過濾
    When 執行 chunk 過濾
    Then 所有 chunks 應被保留

  Scenario: 全部被過濾時回傳空列表
    Given 一組全部為低品質的 chunks
    When 執行 chunk 過濾
    Then 應回傳空的 accepted 列表
