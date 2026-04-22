Feature: Retrieval Playground（除錯用檢索測試台）
  作為 KB Studio 管理員
  我希望輸入查詢看到 top-K 命中 chunks + score + 實際使用的 filter expression
  以便除錯「為何使用者問 X 沒回到 Y」

  Scenario: 正常檢索回 top-K 結果含 score
    Given 租戶 "T001" 的 KB "kb-1" 有已 embed 的 chunks
    When 我以 tenant "T001" 身分呼叫 test_retrieval(kb_id="kb-1", query="退貨", top_k=5)
    Then 回傳 results 應最多 5 筆
    And 每筆應有 chunk_id + content + score
    And 回傳 filter_expr 應為字串含 "tenant_id"

  Scenario: Tenant filter 必帶（安全紅線）
    Given 租戶 "T001" 與 "T002" 的 KB 都有 "退貨" 相關 chunks
    When 我以 tenant "T001" 身分呼叫 test_retrieval(kb_id="kb-1", query="退貨")
    Then 回傳 results 應只含 tenant "T001" 的 chunks
    And 回傳 filter_expr 應含 "tenant_id" 關鍵字

  Scenario: Cross-search 啟用時合併 conv_summaries
    Given 租戶 "T001" 的 KB 有相關 chunks
    And 租戶 "T001" 的 conv_summaries 也有相關對話摘要
    When 我呼叫 test_retrieval(kb_id="kb-1", query="退貨", include_conv_summaries=True)
    Then 回傳 results 應含 source="chunk" 與 source="conv_summary" 兩種類型

  Scenario: 跨租戶 playground 被擋
    Given 租戶 "T001" 擁有 KB "kb-1"
    When 我以 tenant "T002" 身分呼叫 test_retrieval(kb_id="kb-1", query="test")
    Then 應拋出 EntityNotFoundError
