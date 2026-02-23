Feature: Process Document
  非同步文件處理：分塊 → 向量化 → 存入 VectorStore

  Scenario: 成功處理文件
    Given 一個待處理的文件和處理任務
    When 執行文件處理
    Then 任務狀態變為 "completed"
    And 文件狀態變為 "processed"
    And chunk 數量大於 0

  Scenario: 處理失敗時記錄錯誤
    Given 一個待處理的文件和處理任務
    And 分塊服務會拋出例外
    When 執行文件處理
    Then 任務狀態變為 "failed"
    And 任務包含錯誤訊息

  Scenario: 查詢處理任務狀態
    Given 一個已存在的處理任務
    When 查詢該任務狀態
    Then 回傳任務詳細資訊
