Feature: 文件分塊品質指標
  身為知識庫管理員
  我希望系統能自動計算分塊品質分數
  以便我了解分塊品質並進行改善

  Scenario: 正常品質分塊 — 分數為 1.0
    Given 一組正常品質的 chunks
    When 計算品質分數
    Then 品質分數應為 1.0
    And 品質問題列表應為空

  Scenario: 過短分塊 — 扣分 too_short
    Given 一組有超過 20% 過短的 chunks
    When 計算品質分數
    Then 品質分數應為 0.7
    And 品質問題應包含 "too_short"

  Scenario: 斷句問題 — 扣分 mid_sentence_break
    Given 一組有超過 30% 斷句不完整的 chunks
    When 計算品質分數
    Then 品質分數應為 0.8
    And 品質問題應包含 "mid_sentence_break"

  Scenario: 高變異度 — 扣分 high_variance
    Given 一組有高變異度的 chunks
    When 計算品質分數
    Then 品質分數應為 0.8
    And 品質問題應包含 "high_variance"

  Scenario: 多重問題 — 累計扣分
    Given 一組有過短且斷句不完整的 chunks
    When 計算品質分數
    Then 品質分數應為 0.5
    And 品質問題應包含 "too_short"
    And 品質問題應包含 "mid_sentence_break"

  Scenario: 空 chunks — 分數為 0.0
    Given 空的 chunks 列表
    When 計算品質分數
    Then 品質分數應為 0.0

  Scenario: 文件處理後品質已儲存
    Given 一個待處理的文件和處理任務（含品質計算）
    When 執行文件處理（含品質計算）
    Then 品質分數應已儲存至文件

  Scenario: 分頁查詢 chunks
    Given 一個文件有 5 個 chunks
    When 分頁查詢第 1 頁每頁 2 個
    Then 應回傳 2 個 chunks 且總數為 5

  Scenario: 重新處理文件
    Given 一個已處理的文件
    When 執行重新處理
    Then 舊 chunks 應被刪除
    And 新 chunks 應被建立
    And 品質分數應已重新計算

  Scenario: 重新處理時建立 ProcessingTask
    Given 一個已處理的文件
    When 開始重新處理
    Then 應回傳 ProcessingTask 且狀態為 pending

  Scenario: 重新處理失敗時 task 狀態為 failed
    Given 一個已處理的文件（處理會失敗）
    When 執行重新處理（會失敗）
    Then ProcessingTask 狀態應更新為 failed
