Feature: Vectorization
  向量化服務能將文字 chunks 轉為向量並存入 VectorStore

  Scenario: 成功將 chunks 向量化
    Given 3 個文字 chunks
    When 執行向量化
    Then 產生 3 個 1536 維向量

  Scenario: 向量 upsert 帶 tenant_id metadata
    Given 3 個文字 chunks 屬於 tenant "tenant-789"
    When 執行向量 upsert 到 collection "kb_test"
    Then upsert 的每筆 payload 包含 tenant_id "tenant-789"

  Scenario: Fake embedding 回傳固定維度向量
    Given 一段文字 "Hello World"
    When 使用 FakeEmbeddingService 進行 embed
    Then 回傳 1536 維向量
