Feature: Bot 與 Worker 的 Per-Tool RAG 參數
  作為機器人管理員，我要能為不同工具設定不同的 RAG 參數
  讓 rag_query 與 query_dm_with_image 等檢索類工具可以獨立調整 top_k / threshold / reranking
  當 Worker 有覆蓋時，用 Worker 設定；否則沿用 Bot 的 per-tool；最後才用 Bot 全域預設

  Scenario: ToolRagConfig 預設全部為 None
    When 建立一個空的 ToolRagConfig
    Then 所有欄位應為 None

  Scenario: Bot 新增一個工具的 per-tool RAG 設定
    Given 一個 Bot 預設 rag_top_k=5 且 rag_score_threshold=0.3
    When 為 Bot 的 "rag_query" 工具設定 top_k=3
    Then Bot 的 tool_configs 中 "rag_query" 的 rag_top_k 應為 3
    And Bot 的 tool_configs 中 "rag_query" 的 rag_score_threshold 應為 None

  Scenario: 工具未設定 per-tool 時，繼承 Bot 全域預設
    Given 一個 Bot 預設 rag_top_k=5 rag_score_threshold=0.3 rerank_enabled=False
    And Bot 沒有 "rag_query" 的 per-tool 設定
    When 解析 "rag_query" 的最終 RAG 參數
    Then rag_top_k 應為 5
    And rag_score_threshold 應為 0.3
    And rerank_enabled 應為 False

  Scenario: 工具 per-tool 部分覆蓋 Bot 預設
    Given 一個 Bot 預設 rag_top_k=5 rag_score_threshold=0.3 rerank_enabled=False
    And Bot 的 "query_dm_with_image" 工具設定 top_k=10
    When 解析 "query_dm_with_image" 的最終 RAG 參數
    Then rag_top_k 應為 10
    And rag_score_threshold 應為 0.3
    And rerank_enabled 應為 False

  Scenario: Worker per-tool 覆蓋 Bot per-tool
    Given 一個 Bot 預設 rag_top_k=5 rag_score_threshold=0.3
    And Bot 的 "rag_query" 工具設定 top_k=8
    And Worker 的 "rag_query" 工具設定 top_k=20
    When 解析 Worker 下 "rag_query" 的最終 RAG 參數
    Then rag_top_k 應為 20
    And rag_score_threshold 應為 0.3

  Scenario: Worker 無該工具設定時，沿用 Bot per-tool
    Given 一個 Bot 預設 rag_top_k=5 rag_score_threshold=0.3
    And Bot 的 "rag_query" 工具設定 top_k=8
    And Worker 沒有 "rag_query" 的 per-tool 設定
    When 解析 Worker 下 "rag_query" 的最終 RAG 參數
    Then rag_top_k 應為 8
    And rag_score_threshold 應為 0.3

  Scenario: Rerank 設定繼承鏈
    Given 一個 Bot 全域 rerank_enabled=True rerank_model="haiku" rerank_top_n=20
    And Bot 的 "rag_query" 工具設定 rerank_enabled=False
    When 解析 "rag_query" 的最終 RAG 參數
    Then rerank_enabled 應為 False
    And rerank_model 應為 "haiku"
    And rerank_top_n 應為 20
