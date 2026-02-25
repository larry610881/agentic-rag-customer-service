Feature: Dynamic LLM Factory
  DB 優先、.env 兜底的 LLM Service 解析

  Scenario: DB 有啟用設定時使用 DB 設定
    Given DB 中有一個啟用的 LLM 供應商設定
    When 工廠解析 LLM 服務
    Then 應回傳 DB 來源的 LLM 服務

  Scenario: DB 無設定時 fallback 到 .env
    Given DB 中沒有任何 LLM 供應商設定
    When 工廠解析 LLM 服務
    Then 應回傳 fallback 的 LLM 服務

  Scenario: DB 設定全停用時 fallback 到 .env
    Given DB 中的 LLM 供應商設定全部停用
    When 工廠解析 LLM 服務
    Then 應回傳 fallback 的 LLM 服務
