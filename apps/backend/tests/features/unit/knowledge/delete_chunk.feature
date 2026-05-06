Feature: 單一 Chunk 刪除（透過 Outbox Pattern）
  作為 KB Studio 管理員
  我希望能刪除不需要的 chunk
  Phase D 改寫：Milvus DELETE 改走 outbox 事件，drain worker 接手
  PG delete + outbox publish 同 transaction（atomic 帶 publish 一起 commit）

  Scenario: 成功刪除 chunk — DB 清掉 + 發布 outbox vector.delete 事件
    Given 租戶 "T001" 的 chunk "chunk-1" 存在於 DB 與 Milvus collection "kb_kb-1"
    When 我以 tenant "T001" 身分 DELETE chunk "chunk-1"
    Then chunk 應從 DB 刪除
    And 應發布 1 筆 vector.delete outbox 事件
    And 該事件的 collection 應為 "kb_kb-1"
    And 該事件的 filters.id 應為 "chunk-1"
    And 該事件不應帶 doc_watermark_ts
    And 不應直接呼叫 vector store

  Scenario: 跨租戶刪除被擋（tenant chain）
    Given 租戶 "T001" 擁有 chunk "chunk-1"
    When 我以 tenant "T002" 身分嘗試 DELETE chunk "chunk-1"
    Then 應拋出 EntityNotFoundError
    And 不應發布任何 outbox 事件
    And chunk 應保持存在於 DB
