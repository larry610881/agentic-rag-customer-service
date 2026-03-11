Feature: 診斷規則套用
  確保品質評估使用可編輯的規則產生 hints

  Scenario: 使用自訂門檻產生診斷提示
    Given 自訂規則將 context_precision 門檻設為 0.6
    And 評估結果中 context_precision 分數為 0.5
    When 執行診斷分析
    Then 應產生 warning 等級的診斷提示

  Scenario: 使用自訂交叉規則產生診斷提示
    Given 自訂交叉規則 precision > 0.7 且 recall <= 0.4 時觸發
    And 評估結果 precision 為 0.8 且 recall 為 0.3
    When 執行診斷分析
    Then 應產生 rag_strategy 類別的交叉診斷提示
