Feature: 單一 Chunk 刪除（DB + Milvus 雙階段）
  作為 KB Studio 管理員
  我希望能刪除不需要的 chunk
  以便精煉 KB 內容品質

  Scenario: 成功刪除 chunk（DB + Milvus 都清掉）
    Given 租戶 "T001" 的 chunk "chunk-1" 存在於 DB 與 Milvus collection "kb_kb-1"
    When 我以 tenant "T001" 身分 DELETE chunk "chunk-1"
    Then chunk 應從 DB 刪除
    And Milvus collection "kb_kb-1" 的 id "chunk-1" 應被刪除
    And 應記錄 audit event "kb_studio.chunk.delete"

  Scenario: Milvus 刪除失敗不擋 DB 刪除
    Given 租戶 "T001" 的 chunk "chunk-1" 存在
    And Milvus 刪除呼叫會失敗
    When 我以 tenant "T001" 身分 DELETE chunk "chunk-1"
    Then chunk 應從 DB 刪除
    And 應記錄 structlog warning "chunk.delete.milvus_failed" 含 chunk_id
    And use case 應正常回傳（不拋例外）

  Scenario: 跨租戶刪除被擋（tenant chain）
    Given 租戶 "T001" 擁有 chunk "chunk-1"
    When 我以 tenant "T002" 身分嘗試 DELETE chunk "chunk-1"
    Then 應拋出 EntityNotFoundError
    And chunk 應保持存在於 DB 與 Milvus
