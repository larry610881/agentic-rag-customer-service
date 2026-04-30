Feature: Bot-level RAG retrieval modes (Issue #43)
  QueryRAGUseCase 支援 raw / rewrite / hyde 多選 retrieval modes
  並行展開 N 條 query → 對每個 KB 並行檢索 → union by chunk_id → rerank → top_k

  Scenario: Default mode raw — 單條 query 行為對齊舊版
    Given 租戶 "T001" 的 KB "kb-1" 有 3 筆已 embed 的 chunks
    When 我以 retrieval_modes=["raw"] 查詢 "退貨政策"
    Then 應回傳 3 筆結果
    And mode_queries 應只有 raw 對應原始 query

  Scenario: 多選 raw + rewrite — 兩條 query 並行
    Given 租戶 "T001" 的 KB "kb-1" 有已 embed 的 chunks
    When 我以 retrieval_modes=["raw","rewrite"] 查詢 "退貨"
    Then mode_queries 應包含 raw 與 rewrite 兩個 mode
    And vector store 應收到 2 條搜尋呼叫
    And rewrite query 字串可不同於原始 query

  Scenario: 多選 union by chunk_id — 同一 chunk 被多 mode 命中只算一次
    Given 兩條 mode query 命中相同 chunk_id 集合
    When 執行 multi-mode 檢索
    Then 結果應 union by chunk_id（保留最高分）
    And 結果筆數不應超過 unique chunk 數

  Scenario: HyDE only — 用假答案做檢索
    Given 租戶 "T001" 的 KB "kb-1" 有已 embed 的 chunks
    When 我以 retrieval_modes=["hyde"] 查詢 "如何申請退貨"
    Then mode_queries 應只含 hyde
    And vector store 應收到 1 條搜尋呼叫
    And hyde 對應字串可不同於原始 query

  Scenario: 空 modes 應 raise ValueError
    Given 租戶 "T001" 的 KB "kb-1" 有已 embed 的 chunks
    When 我以空 retrieval_modes 查詢
    Then 應 raise ValueError

  Scenario: Bot context 透過 bot_system_prompt 傳遞給 rewrite
    Given 設定 bot_system_prompt 為 "你是家樂福客服"
    When 我以 retrieval_modes=["rewrite"] + 該 bot context 查詢
    Then rewrite_query helper 應收到該 bot_system_prompt
