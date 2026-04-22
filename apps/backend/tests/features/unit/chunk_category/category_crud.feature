Feature: Chunk Category CRUD + 批次指派
  作為 KB Studio 管理員
  我希望能新增 / 刪除分類 + 把 chunks 批次歸到某分類
  以便精煉 auto-classification 的結果

  Scenario: 成功建立分類
    Given 租戶 "T001" 擁有 KB "kb-1"
    When 我以 tenant "T001" 身分 POST /kb/kb-1/categories name="重要 FAQ"
    Then 應建立一個分類 name="重要 FAQ" kb_id="kb-1"
    And 分類的 chunk_count 應為 0
    And 應記錄 audit event "kb_studio.category.create"

  Scenario: 跨租戶建立分類被擋
    Given 租戶 "T001" 擁有 KB "kb-1"
    When 我以 tenant "T002" 身分 POST /kb/kb-1/categories name="駭"
    Then 應拋出 EntityNotFoundError（回 404 防枚舉）
    And 不應建立任何分類

  Scenario: 刪除分類級聯把 chunks 設 NULL
    Given 租戶 "T001" 的 KB "kb-1" 有分類 "cat-A" 含 3 個 chunks
    When 我以 tenant "T001" 身分 DELETE /kb/kb-1/categories/cat-A
    Then 分類 "cat-A" 應被刪除
    And 3 個 chunks 的 category_id 應變為 NULL
    And 應記錄 audit event "kb_studio.category.delete" 含 chunk_count=3

  Scenario: 批次指派 chunks 到分類
    Given 租戶 "T001" 的 KB "kb-1" 有分類 "cat-A"
    And 有 5 個 chunks ["c1","c2","c3","c4","c5"] 屬於 kb-1
    When 我以 tenant "T001" 身分 POST /kb/kb-1/categories/cat-A/assign-chunks body={"chunk_ids":["c1","c3","c5"]}
    Then chunks c1, c3, c5 的 category_id 應變為 "cat-A"
    And chunks c2, c4 的 category_id 應保持不變
    And 應記錄 audit event "kb_studio.category.assign" 含 chunk_count=3

  Scenario: 跨租戶 assign 被擋
    Given 租戶 "T001" 擁有 KB "kb-1" 分類 "cat-A" 與 chunk "c1"
    When 我以 tenant "T002" 身分 POST /kb/kb-1/categories/cat-A/assign-chunks body={"chunk_ids":["c1"]}
    Then 應拋出 EntityNotFoundError
    And chunk "c1" 的 category_id 應保持原樣
