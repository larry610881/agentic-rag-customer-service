Feature: 單一 Chunk 重新向量化（arq job）
  作為系統
  我希望在 chunk 內容改動時僅重算該 chunk 的向量
  以便避免整文 reprocess 的 N×成本

  Scenario: arq job 成功重算單 chunk
    Given chunk "chunk-1" 屬於 KB "kb-1" 租戶 "T001"
    And chunk 的 content = "修正後內容" context_text = "context X"
    When arq worker 執行 reembed_chunk job(chunk_id="chunk-1")
    Then 應呼叫 embedding service 計算 content + context_text 的向量
    And Milvus collection "kb_kb-1" 應呼叫 upsert_single(id="chunk-1", vector, payload)
    And Milvus payload 應含 tenant_id="T001"（安全紅線）
    And 應記錄 token usage（type=embedding, tenant_id=T001）
    And 應記錄 audit event "kb_studio.chunk.reembed" 含 model + token_cost

  Scenario: chunk 已不存在（刪除 + reembed race）
    Given 在 arq job 排隊期間 chunk "chunk-1" 被刪除
    When arq worker 執行 reembed_chunk job(chunk_id="chunk-1")
    Then 應記錄 structlog warning "chunk.reembed.not_found"
    And 不應呼叫 embedding service
    And 不應呼叫 Milvus upsert_single

  Scenario: embedding service 失敗時不動 Milvus
    Given chunk "chunk-1" 存在
    And embedding service 呼叫會失敗
    When arq worker 執行 reembed_chunk job(chunk_id="chunk-1")
    Then 不應呼叫 Milvus upsert_single
    And 應記錄 structlog error "chunk.reembed.embedding_failed"
