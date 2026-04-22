Feature: KB Studio Admin API 整合測試
  端到端驗證 13 個新 endpoint 從 HTTP → Router → Use case → Repo → DB → HTTP

  # Chunk 6 endpoints
  Scenario: 系統管理員分頁列 KB chunks
    Given 系統已 seed KB "kb-1" 含 120 chunks
    And 系統管理員已登入
    When 我送出 GET /api/v1/admin/knowledge-bases/kb-1/chunks?page=1&page_size=50
    Then 回應狀態碼為 200
    And 回應 items 為 50 筆
    And 回應 total 為 120

  Scenario: 系統管理員編輯 chunk content
    Given 系統已 seed chunk "chunk-1" 於 doc "doc-1" 於 kb "kb-1"
    And 系統管理員已登入
    When 我送出 PATCH /api/v1/admin/documents/doc-1/chunks/chunk-1 body={"content":"新內容"}
    Then 回應狀態碼為 200
    And 資料庫中 chunk-1 的 content 為 "新內容"
    And 應 enqueue reembed_chunk job

  Scenario: 跨租戶編輯 chunk 回 404
    Given 系統已 seed chunk "chunk-1" 屬租戶 "T001"
    And 租戶 "T002" 的 tenant_admin 已登入
    When 我送出 PATCH /api/v1/admin/documents/doc-1/chunks/chunk-1 body={"content":"惡意"}
    Then 回應狀態碼為 404

  Scenario: 系統管理員刪除 chunk
    Given 系統已 seed chunk "chunk-1"
    And 系統管理員已登入
    When 我送出 DELETE /api/v1/admin/chunks/chunk-1
    Then 回應狀態碼為 204
    And 資料庫中 chunk-1 不存在

  Scenario: Retrieval Playground 正確回 top-K
    Given 系統已 seed KB "kb-1" 含 embedded chunks
    And 系統管理員已登入
    When 我送出 POST /api/v1/admin/knowledge-bases/kb-1/retrieval-test body={"query":"退貨","top_k":5}
    Then 回應狀態碼為 200
    And 回應 results 長度 <= 5
    And 回應 filter_expr 含 "tenant_id"

  Scenario: 系統管理員取得 KB quality summary
    Given 系統已 seed KB "kb-1" 含多個 quality_flag 的 chunks
    And 系統管理員已登入
    When 我送出 GET /api/v1/admin/knowledge-bases/kb-1/quality-summary
    Then 回應狀態碼為 200
    And 回應 low_quality_count 為整數
    And 回應 avg_cohesion_score 為浮點數

  # Category 3 endpoints
  Scenario: 系統管理員建立分類
    Given 系統已 seed KB "kb-1"
    And 系統管理員已登入
    When 我送出 POST /api/v1/knowledge-bases/kb-1/categories body={"name":"重要 FAQ"}
    Then 回應狀態碼為 201
    And 回應 name 為 "重要 FAQ"

  Scenario: 系統管理員刪除分類（級聯）
    Given 系統已 seed 分類 "cat-A" 於 KB "kb-1" 含 3 chunks
    And 系統管理員已登入
    When 我送出 DELETE /api/v1/knowledge-bases/kb-1/categories/cat-A
    Then 回應狀態碼為 204
    And 3 chunks 的 category_id 為 NULL

  Scenario: 系統管理員批次指派 chunks 到分類
    Given 系統已 seed 分類 "cat-A" 與 5 個 chunks ["c1","c2","c3","c4","c5"]
    And 系統管理員已登入
    When 我送出 POST /api/v1/knowledge-bases/kb-1/categories/cat-A/assign-chunks body={"chunk_ids":["c1","c3","c5"]}
    Then 回應狀態碼為 200
    And chunks c1, c3, c5 的 category_id 為 "cat-A"

  # Milvus 3 endpoints
  Scenario: 系統管理員列 Milvus collections
    Given 系統已 seed 3 個 Milvus collections
    And 系統管理員已登入
    When 我送出 GET /api/v1/admin/milvus/collections
    Then 回應狀態碼為 200
    And 回應含 3 個 collection
    And 每個 collection 的 tenant_id index_type 為 "INVERTED"

  Scenario: 系統管理員取得 collection 詳細統計
    Given 系統已 seed Milvus collection "kb_kb-1" 含 100 rows
    And 系統管理員已登入
    When 我送出 GET /api/v1/admin/milvus/collections/kb_kb-1/stats
    Then 回應狀態碼為 200
    And 回應 row_count 為 100
    And 回應 loaded 為 true

  Scenario: 系統管理員觸發 rebuild index
    Given 系統已 seed Milvus collection "kb_new-kb"（模擬新 collection）
    And 系統管理員已登入
    When 我送出 POST /api/v1/admin/milvus/collections/kb_new-kb/rebuild-index
    Then 回應狀態碼為 202
    And 應記錄 audit event "kb_studio.milvus.rebuild_index"

  # Conv Summary 2 endpoints
  Scenario: 系統管理員列對話摘要
    Given 租戶 "T001" 有 5 筆 conv_summaries
    And 系統管理員已登入
    When 我送出 GET /api/v1/admin/conv-summaries?tenant_id=T001
    Then 回應狀態碼為 200
    And 回應 items 為 5 筆

  Scenario: 一般租戶不可列 admin conv-summaries 端點
    Given 一般租戶已登入
    When 我送出 GET /api/v1/admin/conv-summaries?tenant_id=T001
    Then 回應狀態碼為 403
