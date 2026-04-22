Feature: Admin Pricing API 整合測試
  系統管理員可透過 /api/v1/admin/pricing 管理模型定價版本
  並可執行回溯重算；一般租戶無權呼叫

  Scenario: 系統管理員可建立新 pricing 版本
    Given 系統管理員已登入
    When 我送出 POST /api/v1/admin/pricing body={"provider":"openai","model_id":"gpt-5-mini","display_name":"GPT-5 Mini","input_price":0.25,"output_price":2.0,"cache_read_price":0.025,"cache_creation_price":0,"effective_from":"FUTURE","note":"測試上架"}
    Then 回應狀態碼為 201
    And 回應中 provider 為 "openai"
    And 回應中 model_id 為 "gpt-5-mini"
    And 回應中 effective_to 為 null

  Scenario: 系統管理員可列出 pricing 版本
    Given 系統已 seed pricing "anthropic" "claude-haiku-4-5" 生效中
    And 系統管理員已登入
    When 我送出 GET /api/v1/admin/pricing?provider=anthropic
    Then 回應狀態碼為 200
    And 回應 items 至少含一筆 provider 為 "anthropic"

  Scenario: 一般租戶呼叫 admin pricing 端點回 403
    Given 一般租戶已登入
    When 我送出 GET /api/v1/admin/pricing
    Then 回應狀態碼為 403

  Scenario: 系統管理員可停用某 pricing 版本
    Given 系統已 seed pricing "openai" "gpt-5" 生效中 id 為 "pricing-xyz"
    And 系統管理員已登入
    When 我送出 POST /api/v1/admin/pricing/pricing-xyz/deactivate
    Then 回應狀態碼為 200
    And 回應中 effective_to 不為 null

  Scenario: 系統管理員可執行回溯重算 dry-run → execute
    Given token_usage_records 在過去 1 小時有 2 筆 "anthropic:claude-haiku-4-5" usage
    And 系統已 seed 新版本 pricing "anthropic" "claude-haiku-4-5" input=1.20 output=6.00
    And 系統管理員已登入
    When 我送出 POST /api/v1/admin/pricing/recalculate:dry-run body 含 pricing_id 與過去 1 小時區間
    Then 回應狀態碼為 200
    And 回應 affected_rows 為 2
    And 回應含有 dry_run_token
    When 我送出 POST /api/v1/admin/pricing/recalculate:execute body 含該 dry_run_token 與 reason="補算"
    Then 回應狀態碼為 200
    And 回應 affected_rows 為 2

  Scenario: 回溯重算歷史可查詢
    Given 系統已執行過 1 次 recalculate audit
    And 系統管理員已登入
    When 我送出 GET /api/v1/admin/pricing/recalculate-history
    Then 回應狀態碼為 200
    And 回應 items 至少含一筆 reason 不為空
