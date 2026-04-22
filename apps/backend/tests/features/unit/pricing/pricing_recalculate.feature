Feature: Pricing 回溯重算 (Dry-run + Execute)
  作為系統管理員
  我希望能補算過去某段區間的 estimated_cost
  以應對廠商調價延後發現的情境，且每次重算可稽核、可 rollback

  Scenario: Dry-run 正確回傳影響筆數與成本差
    Given token_usage_records 有 3 筆 "anthropic:claude-haiku-4-5" usage 在過去 1 小時
    And 每筆 input_tokens=1000 output_tokens=500 estimated_cost=0.0035
    Given 已建立新版本 pricing input=1.10 output=5.50
    When 我以該 pricing 對「過去 1 小時」區間 dry-run
    Then 回傳 affected_rows 應為 3
    And 回傳 cost_before_total 應為 0.0105
    And 回傳 cost_after_total 應大於 cost_before_total
    And 回傳應含有 dry_run_token

  Scenario: Execute 無 token 會被擋
    When 我執行 recalculate execute 不帶 dry_run_token
    Then 應拋出 PermissionError 訊息包含 "token required"

  Scenario: Execute 的 token 過期會被擋
    Given 已取得 dry_run_token 但 TTL 已過期
    When 我用該 token 執行 recalculate execute
    Then 應拋出 PermissionError 訊息包含 "expired"

  Scenario: Execute 時偵測到 race（期間新增 usage）會 abort
    Given dry-run 回傳 affected_rows=3
    And dry-run 之後 token_usage_records 又多了 2 筆符合條件的 row
    When 我用 dry_run_token 執行 recalculate execute
    Then 應拋出 RuntimeError 訊息包含 "race"
    And token_usage_records 應保持原 estimated_cost 不變

  Scenario: Execute 成功會寫入 audit 並更新 cost_recalc_at
    Given dry-run 回傳 affected_rows=3 cost_delta=+0.00035
    When 我用 dry_run_token 執行 recalculate execute reason="OpenAI 6/15 官方調價"
    Then pricing_recalc_audit 應新增 1 筆紀錄 executed_by 為 admin id
    And 該區間的 3 筆 token_usage_records 的 cost_recalc_at 應被設定為當前時間
    And 3 筆 row 的 estimated_cost 應更新為新價格計算值

  Scenario: Dry-run 拒絕過大區間
    Given token_usage_records 在區間內有 150000 筆符合
    When 我對該區間 dry-run
    Then 應拋出 ValueError 訊息包含 "affected rows exceeds limit"
