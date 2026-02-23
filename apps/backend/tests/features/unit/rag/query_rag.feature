Feature: RAG Query
  RAG 查詢用例能結合向量搜尋與 LLM 生成帶引用的回答

  Scenario: 成功查詢知識庫並回傳帶引用的回答
    Given 知識庫 "kb-001" 存在且屬於 tenant "tenant-001"
    And 向量搜尋回傳 2 筆相關結果
    When 執行 RAG 查詢 "退貨政策是什麼"
    Then 應回傳包含回答的 RAGResponse
    And 回答應包含 "根據知識庫"

  Scenario: 回答包含來源文件名稱和內容片段
    Given 知識庫 "kb-001" 存在且屬於 tenant "tenant-001"
    And 向量搜尋回傳 2 筆相關結果
    When 執行 RAG 查詢 "退貨政策是什麼"
    Then 來源列表應包含 2 筆引用
    And 每筆引用應包含文件名稱和內容片段

  Scenario: 查詢無相關知識時拋出 NoRelevantKnowledgeError
    Given 知識庫 "kb-001" 存在且屬於 tenant "tenant-001"
    And 向量搜尋回傳空結果
    When 執行 RAG 查詢 "不存在的主題"
    Then 應拋出 NoRelevantKnowledgeError

  Scenario: 查詢結果正確過濾 tenant_id
    Given 知識庫 "kb-001" 存在且屬於 tenant "tenant-001"
    And 向量搜尋回傳 1 筆相關結果
    When 執行 RAG 查詢 "退貨政策是什麼"
    Then 向量搜尋應使用 tenant_id "tenant-001" 過濾

  Scenario: 知識庫不存在時拋出 EntityNotFoundError
    Given 知識庫 "kb-999" 不存在
    When 執行 RAG 查詢 "任何問題" 到知識庫 "kb-999"
    Then 應拋出 EntityNotFoundError
