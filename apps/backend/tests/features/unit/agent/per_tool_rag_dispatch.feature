Feature: 不同工具使用各自的 RAG 參數
  作為機器人管理員，我希望 rag_query 與 query_dm_with_image 能使用各自的 RAG 參數
  讓圖卡查詢用較高的 top_k，純文字查詢用較低的 top_k

  Scenario: Bot 的 per-tool RAG 參數傳遞到各自的 tool
    Given Bot 全域 rag_top_k=5 rag_score_threshold=0.3
    And Bot 的 "rag_query" 工具覆蓋 top_k=3
    And Bot 的 "query_dm_with_image" 工具覆蓋 top_k=10
    When 為這個 Bot 組裝工具參數 (tool_rag_params)
    Then "rag_query" 的 rag_top_k 應為 3
    And "query_dm_with_image" 的 rag_top_k 應為 10
    And 兩個工具的 rag_score_threshold 應都為 0.3

  Scenario: Worker 覆蓋 Bot 的 per-tool 設定
    Given Bot 全域 rag_top_k=5 rag_score_threshold=0.3
    And Bot 的 "rag_query" 工具覆蓋 top_k=3
    And Worker 的 "rag_query" 工具覆蓋 top_k=20
    When 為這個 Worker 組裝工具參數 (tool_rag_params)
    Then "rag_query" 的 rag_top_k 應為 20

  Scenario: 沒有 per-tool 設定時使用 Bot 全域預設
    Given Bot 全域 rag_top_k=5 rag_score_threshold=0.3
    And Bot 沒有任何 per-tool 設定
    When 為這個 Bot 組裝工具參數 (tool_rag_params)
    Then "rag_query" 的 rag_top_k 應為 5
    And "query_dm_with_image" 的 rag_top_k 應為 5
