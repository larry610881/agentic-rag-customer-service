Feature: arq Worker job 自動 retry（Layer 1 — Resilience Wrapper）
  作為 worker 維運者，我要 transient infra 短暫失敗能自動指數退避重試 3 次，
  permanent 設定錯誤直接落 DLQ 不浪費 quota，最終失敗時 processing_task
  狀態確實標 failed 方便 admin 介入。
  動機：5/6 carrefour DM 重 process 出現 page 50/54/55 三個 transient
  failures 必須 user 手動 reprocess，本 layer 讓未來這類短暫故障自動恢復。

  Scenario: transient 例外（MilvusException）觸發 Retry(defer=5)
    Given worker 的 job_try 為 1
    And 內層業務拋 MilvusException 連線失敗
    When 執行包了 resilience wrapper 的任務
    Then 應該 raise arq.Retry，defer 為 5 秒
    And processing_task 不應被標記為 failed

  Scenario: permanent 例外（ValueError）不 retry，processing_task 直接標 failed
    Given worker 的 job_try 為 1
    And 內層業務拋 ValueError 空 API key
    When 執行包了 resilience wrapper 的任務
    Then 不應拋出例外給 arq
    And processing_task 應被標 status=failed
    And processing_task error_message 應包含 "ValueError"

  Scenario: transient 但 job_try=3 已用盡重試次數
    Given worker 的 job_try 為 3
    And 內層業務拋 MilvusException 連線失敗
    When 執行包了 resilience wrapper 的任務
    Then 應拋出原始 MilvusException
    And processing_task 應被標 status=failed
    And processing_task error_message 應包含 "attempt=3"

  Scenario: 業務成功 → 回傳結果
    Given worker 的 job_try 為 1
    And 內層業務回傳 "ok"
    When 執行包了 resilience wrapper 的任務
    Then 應拿到 "ok" 結果
    And processing_task 不應被標記為 failed

  Scenario: HTTP 401 屬於 permanent（不 retry）
    Given worker 的 job_try 為 1
    And 內層業務拋 httpx.HTTPStatusError 狀態碼 401
    When 執行包了 resilience wrapper 的任務
    Then 不應拋出例外給 arq
    And processing_task 應被標 status=failed

  Scenario: HTTP 503 屬於 transient（觸發 Retry）
    Given worker 的 job_try 為 1
    And 內層業務拋 httpx.HTTPStatusError 狀態碼 503
    When 執行包了 resilience wrapper 的任務
    Then 應該 raise arq.Retry，defer 為 5 秒

  Scenario: job_try=2 時 backoff 升至 30 秒
    Given worker 的 job_try 為 2
    And 內層業務拋 MilvusException 連線失敗
    When 執行包了 resilience wrapper 的任務
    Then 應該 raise arq.Retry，defer 為 30 秒
