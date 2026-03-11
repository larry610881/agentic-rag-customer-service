Feature: RAG Quality Diagnostic
  品質診斷引擎根據評估分數產生改善提示

  Scenario: 低 context_precision 觸發資料源診斷
    Given 評估維度 context_precision 分數為 0.2
    When 執行診斷
    Then 應產生 category 為 "data_source" severity 為 "critical" 的提示

  Scenario: 中等 faithfulness 觸發 prompt 警告
    Given 評估維度 faithfulness 分數為 0.4
    When 執行診斷
    Then 應產生 category 為 "prompt" severity 為 "warning" 的提示

  Scenario: 高 precision 低 recall 觸發組合診斷
    Given 評估維度 context_precision 分數為 0.9
    And 評估維度 context_recall 分數為 0.2
    When 執行診斷
    Then 應包含建議 "增加 top_k"

  Scenario: 所有分數正常不產生提示
    Given 評估維度 context_precision 分數為 0.85
    And 評估維度 faithfulness 分數為 0.9
    When 執行診斷
    Then 診斷結果為空
