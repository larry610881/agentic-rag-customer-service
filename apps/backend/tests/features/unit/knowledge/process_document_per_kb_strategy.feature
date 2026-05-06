Feature: Per-KB Chunk Strategy 路由
  KB.chunk_strategy 設值時，ProcessDocumentUseCase 應從 text_splitter_overrides
  選對應 splitter；沒設值時走預設。LLM contextual retrieval 步驟若 chunk
  已有 context_text（splitter 已填）則跳過該 chunk，避免覆蓋 splitter 結果。

  Scenario: KB.chunk_strategy=separator 路由到 separator splitter
    Given KB chunk_strategy 設為 separator
    And text_splitter_overrides 含 separator splitter
    When ProcessDocumentUseCase 執行 chunking
    Then 應呼叫 separator splitter 而非預設 splitter

  Scenario: chunk 已有 context_text 應跳過 LLM contextual retrieval
    Given KB context_model 已設定
    And chunks 含 1 個有 context_text 與 1 個無 context_text
    When ProcessDocumentUseCase 執行 contextual retrieval 步驟
    Then 只對無 context_text 的 chunk 呼叫 LLM
