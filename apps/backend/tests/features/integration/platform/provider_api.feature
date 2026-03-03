Feature: Provider Settings API Integration
  使用真實 DB 驗證 Provider Settings CRUD API

  Scenario: 成功建立 Provider Setting
    When 我送出 POST /api/v1/settings/providers 類型 "llm" 名稱 "openai" 顯示名稱 "OpenAI"
    Then 回應狀態碼為 201
    And 回應包含 provider_name 為 "openai"
    And 回應包含 has_api_key 為 true

  Scenario: 重複建立回傳 409
    Given 已建立 Provider "llm" "openai" "OpenAI"
    When 我送出 POST /api/v1/settings/providers 類型 "llm" 名稱 "openai" 顯示名稱 "OpenAI 2"
    Then 回應狀態碼為 409

  Scenario: 查詢 Provider 列表
    Given 已建立 Provider "llm" "openai" "OpenAI"
    Given 已建立 Provider "embedding" "qwen" "Qwen Embed"
    When 我送出 GET /api/v1/settings/providers
    Then 回應狀態碼為 200
    And 回應包含 2 個 Provider

  Scenario: 按類型篩選 Provider
    Given 已建立 Provider "llm" "openai" "OpenAI"
    Given 已建立 Provider "embedding" "qwen" "Qwen Embed"
    When 我送出 GET /api/v1/settings/providers?type=llm
    Then 回應狀態碼為 200
    And 回應包含 1 個 Provider

  Scenario: 查詢單一 Provider
    Given 已建立 Provider "llm" "anthropic" "Anthropic"
    When 我用該 Provider ID 送出 GET /api/v1/settings/providers/{id}
    Then 回應狀態碼為 200
    And 回應包含 provider_name 為 "anthropic"

  Scenario: 更新 Provider
    Given 已建立 Provider "llm" "openai" "舊名"
    When 我用該 Provider ID 送出 PUT /api/v1/settings/providers/{id} 顯示名稱 "新名"
    Then 回應狀態碼為 200
    And 回應包含 display_name 為 "新名"

  Scenario: 刪除 Provider
    Given 已建立 Provider "llm" "openai" "待刪除"
    When 我用該 Provider ID 送出 DELETE /api/v1/settings/providers/{id}
    Then 回應狀態碼為 204

  Scenario: 查詢不存在的 Provider 回傳 404
    When 我送出 GET /api/v1/settings/providers/00000000-0000-0000-0000-000000000000
    Then 回應狀態碼為 404
