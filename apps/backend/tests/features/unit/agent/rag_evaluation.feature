Feature: RAG 品質評估
  作為系統，我需要評估 RAG 查詢和回答的品質

  Scenario: L1 評估 — Context Precision 和 Recall
    Given 一個 RAG 評估用例使用 mock LLM
    And LLM 回傳評分 context_precision 0.8 和 context_recall 0.7
    When 執行 L1 評估查詢 "退貨政策" 和 chunks ["30天內可退貨"]
    Then 評估結果的 layer 應為 "L1"
    And 應包含 context_precision 維度分數 0.8
    And 應包含 context_recall 維度分數 0.7

  Scenario: L2 評估 — Faithfulness 和 Relevancy
    Given 一個 RAG 評估用例使用 mock LLM
    And LLM 回傳評分 faithfulness 0.9 和 relevancy 0.85
    When 執行 L2 評估查詢 "退貨政策" 回答 "30天內可退貨" 上下文 "退貨政策原文"
    Then 評估結果的 layer 應為 "L2"
    And 應包含 faithfulness 維度分數 0.9

  Scenario: L3 評估 — Agent 決策效率
    Given 一個 RAG 評估用例使用 mock LLM
    And LLM 回傳評分 agent_efficiency 0.75 和 tool_selection 0.9
    When 執行 L3 評估查詢 "退貨政策" 和工具呼叫記錄
    Then 評估結果的 layer 應為 "L3"
    And 應包含 agent_efficiency 維度分數 0.75

  Scenario: 合併評估 — L1+L2 一次 API call
    Given 一個 RAG 評估用例使用 mock LLM
    And LLM 回傳合併評分 context_precision 0.8 和 faithfulness 0.9
    When 執行合併評估 L1+L2 查詢 "退貨政策" 有 RAG sources
    Then 應只呼叫 LLM 一次
    And 應包含 context_precision 維度分數 0.8
    And 應包含 faithfulness 維度分數 0.9

  Scenario: 合併評估 — MCP-only 自動跳過 L1
    Given 一個 RAG 評估用例使用 mock LLM
    And LLM 回傳合併評分 faithfulness 0.85 和 relevancy 0.9
    When 執行合併評估 L1+L2 查詢 "500元商品" 無 RAG sources
    Then 應只呼叫 LLM 一次
    And 結果不應包含 context_precision 維度
    And 應包含 faithfulness 維度分數 0.85

  Scenario: 合併評估 — 回傳實際 model_name
    Given 一個 RAG 評估用例使用帶有 model_name 的 mock LLM
    When 執行合併評估 L2 查詢 "退貨政策"
    Then 評估結果的 model_used 應為 "gemini-2.5-flash-lite"

  Scenario: EvalResult 平均分數計算
    Given 一個包含多維度的 EvalResult
    Then avg_score 應為各維度分數的平均值
