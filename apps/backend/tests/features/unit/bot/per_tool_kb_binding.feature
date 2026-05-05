Feature: Bot 與 Worker 的 Per-Tool 知識庫綁定（kb_ids）
  作為機器人管理員，我要能為不同工具綁定不同的知識庫
  讓 rag_query 只搜 FAQ KB、query_dm_with_image 只搜 DM KB
  繼承優先序：Worker per-tool kb_ids > Bot per-tool kb_ids > Bot 全域 knowledge_base_ids

  Scenario: 工具未設定 per-tool kb_ids 時，繼承 Bot 全域 KB
    Given 一個 Bot 全域綁定 KB ["kb-faq", "kb-dm"]
    And Bot 沒有 "rag_query" 的 per-tool 設定
    When 解析 "rag_query" 的最終 kb_ids
    Then kb_ids 應為 None

  Scenario: Bot per-tool kb_ids 覆寫 Bot 全域
    Given 一個 Bot 全域綁定 KB ["kb-faq", "kb-dm"]
    And Bot 的 "rag_query" 工具設定 kb_ids=["kb-faq"]
    When 解析 "rag_query" 的最終 kb_ids
    Then kb_ids 應為 ["kb-faq"]

  Scenario: 兩個 RAG 工具各自綁不同 KB
    Given 一個 Bot 全域綁定 KB ["kb-faq", "kb-dm"]
    And Bot 的 "rag_query" 工具設定 kb_ids=["kb-faq"]
    And Bot 的 "query_dm_with_image" 工具設定 kb_ids=["kb-dm"]
    When 解析 "rag_query" 的最終 kb_ids
    Then kb_ids 應為 ["kb-faq"]
    When 解析 "query_dm_with_image" 的最終 kb_ids
    Then kb_ids 應為 ["kb-dm"]

  Scenario: Worker per-tool kb_ids 覆寫 Bot per-tool
    Given 一個 Bot 全域綁定 KB ["kb-faq", "kb-dm"]
    And Bot 的 "rag_query" 工具設定 kb_ids=["kb-faq"]
    And Worker 的 "rag_query" 工具設定 kb_ids=["kb-special"]
    When 解析 Worker 下 "rag_query" 的最終 kb_ids
    Then kb_ids 應為 ["kb-special"]

  Scenario: ToolRagConfig 預設 kb_ids 為 None
    When 建立一個空的 ToolRagConfig
    Then kb_ids 欄位應為 None
