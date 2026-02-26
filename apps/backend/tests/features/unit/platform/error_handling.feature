Feature: BackgroundTask 錯誤捕捉 (Background Task Error Handling)

  Scenario: BackgroundTask 例外應記錄 structured log
    Given 一個會拋出例外的 async 任務
    When 透過 safe_background_task 執行該任務
    Then 例外應被捕捉且不向外傳播
    And 結構化日誌應包含 task_name 與 error 資訊

  Scenario: 正常執行的 BackgroundTask 不應產生錯誤日誌
    Given 一個正常完成的 async 任務
    When 透過 safe_background_task 執行該任務
    Then 任務應正常完成
    And 不應有錯誤日誌產生
