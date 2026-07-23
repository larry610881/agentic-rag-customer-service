Feature: LINE Webhook Worker 直接檢索模式（workflow 快速道）
  意圖分類已判定問題類型的 worker，開啟 direct_retrieval 後
  跳過 ReAct 決策輪：直接以使用者原文檢索綁定知識庫，
  單次 LLM 生成；檢索品質未過門檻自動升級完整 ReAct。

  Scenario: 快速道命中 — 檢索過門檻後單次生成
    Given 一個開啟直接檢索的 Worker 且檢索結果分數高於門檻
    When 系統處理一則命中該 Worker 的 LINE 訊息
    Then Agent 應以無工具模式單次生成
    And 生成 Prompt 應包含檢索結果
    And 回覆來源應來自快速道檢索

  Scenario: 檢索未過門檻 — 自動升級完整 ReAct
    Given 一個開啟直接檢索的 Worker 但檢索結果分數低於門檻
    When 系統處理一則命中該 Worker 的 LINE 訊息
    Then Agent 應以完整工具模式處理

  Scenario: 檢索異常 — 自動升級完整 ReAct
    Given 一個開啟直接檢索的 Worker 但檢索過程拋出例外
    When 系統處理一則命中該 Worker 的 LINE 訊息
    Then Agent 應以完整工具模式處理

  Scenario: 開關關閉 — 行為與現狀完全一致
    Given 一個未開啟直接檢索的 Worker
    When 系統處理一則命中該 Worker 的 LINE 訊息
    Then 不應執行快速道檢索
    And Agent 應以完整工具模式處理

  Scenario: 快速道保留 DM 圖卡 — 並行呼叫 DM 工具
    Given 一個開啟直接檢索且啟用 DM 工具的 Worker
    When 系統處理一則命中該 Worker 的 LINE 訊息
    Then DM 工具應被並行呼叫
    And 回覆應附上 DM 圖卡輪播
    And 生成 Prompt 應包含 DM 型錄內容
