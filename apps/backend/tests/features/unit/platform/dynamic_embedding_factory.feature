Feature: Dynamic Embedding Factory
  固定使用 OpenAI text-embedding-3-small，API key 從 DB (OpenAI LLM) 或 .env 取得

  Scenario: DB 有 OpenAI LLM 設定時使用其 API key
    Given DB 中有 OpenAI LLM 供應商設定含 API key
    When 工廠解析 Embedding 服務
    Then 應回傳 OpenAI Embedding 服務

  Scenario: DB 無設定且 .env 也無 key 時 fallback
    Given DB 中沒有任何供應商設定且 .env 無 OpenAI key
    When 工廠解析 Embedding 服務
    Then 應回傳 fallback 的 Embedding 服務

  Scenario: DB 有設定但無 API key 且 .env 也無 key 時 fallback
    Given DB 中有供應商設定但無 API key 且 .env 無 OpenAI key
    When 工廠解析 Embedding 服務
    Then 應回傳 fallback 的 Embedding 服務

  Scenario: Proxy 委派 embed_texts 到工廠解析的服務
    Given DB 中沒有任何供應商設定且 .env 無 OpenAI key
    When Proxy 呼叫 embed_texts
    Then 應透過 fallback 服務執行 embed_texts

  Scenario: Proxy 委派 embed_query 到工廠解析的服務
    Given DB 中沒有任何供應商設定且 .env 無 OpenAI key
    When Proxy 呼叫 embed_query
    Then 應透過 fallback 服務執行 embed_query
