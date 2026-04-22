Feature: Milvus Collection Dashboard 列表
  作為系統管理員
  我希望看到所有 Milvus collection 與 row count / index 狀態
  以便判斷 infra 健康度與資料增長趨勢

  Scenario: Platform admin 看所有 collections
    Given Milvus 有 collections: "kb_kb-1"(100 rows), "kb_kb-2"(50 rows), "conv_summaries"(200 rows)
    When 我以 platform_admin 身分呼叫 list_collections()
    Then 回傳應含 3 個 collection
    And kb_kb-1 的 tenant_id index_type 應為 "INVERTED"（已 hotfix）
    And conv_summaries 的 tenant_id index_type 應為 "INVERTED"

  Scenario: Tenant admin 只看自己 KB 的 collections
    Given 租戶 "T001" 擁有 2 KBs "kb-1" 與 "kb-2"
    And 租戶 "T002" 擁有 1 KB "kb-3"
    When 我以 tenant "T001" 的 tenant_admin 身分呼叫 list_collections()
    Then 回傳應含 "kb_kb-1" 與 "kb_kb-2"
    And 回傳不應含 "kb_kb-3"（跨租戶）
    And 回傳不應含 "conv_summaries"（platform 專屬）

  Scenario: 顯示每個 collection 的詳細統計
    Given Milvus collection "kb_kb-1" 有 1500 rows
    When 我以 platform_admin 身分呼叫 get_collection_stats("kb_kb-1")
    Then 回傳 row_count 應為 1500
    And 回傳 loaded 應為 True
    And 回傳 indexes 應含 {"field": "tenant_id", "index_type": "INVERTED"}
    And 回傳 indexes 應含 {"field": "document_id", "index_type": "INVERTED"}
    And 回傳 indexes 應含 {"field": "vector", "index_type": "AUTOINDEX"}
