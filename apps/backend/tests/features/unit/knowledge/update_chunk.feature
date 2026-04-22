Feature: Chunk Inline 編輯 + 自動 re-embedding
  作為 KB Studio 管理員
  我希望能直接編輯 chunk 內容並讓系統自動重新向量化
  以便即時修正 RAG 檢索品質而無需重傳整份文件

  Scenario: 成功更新 chunk content 並 enqueue re-embed job
    Given 租戶 "T001" 的 KB "kb-1" 有一個 chunk "chunk-1" content="原始內容"
    When 我以 tenant "T001" 身分 PATCH chunk "chunk-1" 設 content="修正後內容"
    Then chunk 的 content 應更新為 "修正後內容"
    And chunk 的 updated_at 應設為當前時間
    And 應 enqueue arq job "reembed_chunk" 帶 chunk_id="chunk-1"
    And 應記錄 audit event "kb_studio.chunk.update" 含 actor + content_diff_len

  Scenario: 跨租戶編輯被擋下（tenant chain 驗證）
    Given 租戶 "T001" 擁有 chunk "chunk-1"
    When 我以 tenant "T002" 身分嘗試 PATCH chunk "chunk-1" content="惡意內容"
    Then 應拋出 EntityNotFoundError（回 404 防枚舉）
    And chunk 的 content 應保持原樣不變
    And 不應 enqueue 任何 arq job

  Scenario: 只改 context_text 不改 content 也觸發 re-embed
    Given 租戶 "T001" 的 chunk "chunk-1" content="X" context_text="原 context"
    When 我以 tenant "T001" 身分 PATCH chunk "chunk-1" 設 context_text="新 context"
    Then chunk 的 context_text 應更新為 "新 context"
    And 應 enqueue "reembed_chunk" job

  Scenario: 空 content 拒絕更新
    Given 租戶 "T001" 的 chunk "chunk-1" 存在
    When 我以 tenant "T001" 身分 PATCH chunk "chunk-1" content=""
    Then 應拋出 ValueError 訊息含 "content"
