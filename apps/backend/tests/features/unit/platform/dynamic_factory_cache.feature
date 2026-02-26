Feature: Dynamic Factory Redis 快取 (Dynamic Factory Cache)

  Scenario: LLM Factory 第二次呼叫從快取取得設定不查 DB
    Given DB 中有啟用的 LLM 供應商設定且快取已啟用
    When 連續兩次解析 LLM 服務
    Then DB 查詢應只執行一次

  Scenario: Embedding Factory 第二次呼叫從快取取得設定不查 DB
    Given DB 中有啟用的 Embedding 供應商設定且快取已啟用
    When 連續兩次解析 Embedding 服務
    Then DB 查詢應只執行一次
