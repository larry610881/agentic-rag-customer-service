Feature: Dynamic Embedding Factory
  DB 優先、.env 兜底的 Embedding Service 解析

  Scenario: DB 有啟用 Embedding 設定時使用 DB 設定
    Given DB 中有一個啟用的 Embedding 供應商設定
    When 工廠解析 Embedding 服務
    Then 應回傳 DB 來源的 Embedding 服務

  Scenario: DB 無 Embedding 設定時 fallback 到 .env
    Given DB 中沒有任何 Embedding 供應商設定
    When 工廠解析 Embedding 服務
    Then 應回傳 fallback 的 Embedding 服務

  Scenario: DB Embedding 設定全停用時 fallback 到 .env
    Given DB 中的 Embedding 供應商設定全部停用
    When 工廠解析 Embedding 服務
    Then 應回傳 fallback 的 Embedding 服務

  Scenario: Fake provider 回傳 fallback 服務
    Given DB 中有一個啟用的 Fake Embedding 供應商設定
    When 工廠解析 Embedding 服務
    Then 應回傳 fallback 的 Embedding 服務

  Scenario: Proxy 委派 embed_texts 到工廠解析的服務
    Given DB 中沒有任何 Embedding 供應商設定
    When Proxy 呼叫 embed_texts
    Then 應透過 fallback 服務執行 embed_texts

  Scenario: Proxy 委派 embed_query 到工廠解析的服務
    Given DB 中沒有任何 Embedding 供應商設定
    When Proxy 呼叫 embed_query
    Then 應透過 fallback 服務執行 embed_query
