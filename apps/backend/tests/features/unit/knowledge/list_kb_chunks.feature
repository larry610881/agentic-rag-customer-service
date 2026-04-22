Feature: KB 全部 Chunk 分頁列表
  作為 KB Studio 管理員
  我希望跨文件列出整個 KB 的 chunks 並支援分頁 + 分類過濾
  以便在 Chunks tab 以 virtualized list 檢視大量 chunks

  Scenario: 首頁 50 筆
    Given 租戶 "T001" 的 KB "kb-1" 有 120 個 chunks
    When 我以 tenant "T001" 身分呼叫 list_kb_chunks(kb_id="kb-1", page=1, page_size=50)
    Then 回傳 items 應為 50 筆
    And 回傳 total 應為 120
    And 回傳 page 應為 1

  Scenario: 依 category filter
    Given 租戶 "T001" 的 KB "kb-1" 有 chunks：20 筆屬 category "cat-A"、30 筆屬 category "cat-B"、50 筆未分類
    When 我呼叫 list_kb_chunks(kb_id="kb-1", category_id="cat-A")
    Then 回傳 items 應全部屬於 category "cat-A"
    And 回傳 total 應為 20

  Scenario: 跨租戶列 chunks 被擋
    Given 租戶 "T001" 擁有 KB "kb-1"
    When 我以 tenant "T002" 身分呼叫 list_kb_chunks(kb_id="kb-1")
    Then 應拋出 EntityNotFoundError（回 404 防枚舉）

  Scenario: page 超過總頁數回空陣列
    Given 租戶 "T001" 的 KB "kb-1" 有 5 個 chunks
    When 我以 tenant "T001" 身分呼叫 list_kb_chunks(kb_id="kb-1", page=10, page_size=50)
    Then 回傳 items 應為空陣列
    And 回傳 total 應為 5
