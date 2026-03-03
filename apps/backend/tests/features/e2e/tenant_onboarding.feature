Feature: 租戶入駐全流程
  E2E 驗證：建立租戶 → 註冊管理員 → 登入 → 設定 Provider → 驗證

  Scenario: 完整租戶入駐流程
    # Step 1: 建立租戶
    When 我建立租戶 "ACME Corp"
    Then 回應狀態碼為 201
    And 租戶名稱為 "ACME Corp"

    # Step 2: 註冊管理員（關聯租戶）
    When 我為該租戶註冊管理員 "admin@acme.com" 密碼 "secure123"
    Then 回應狀態碼為 201

    # Step 3: 登入取得 token
    When 我以 "admin@acme.com" 密碼 "secure123" 登入
    Then 回應狀態碼為 200
    And 取得有效的 access_token

    # Step 4: 取得租戶 token 並設定 Provider
    When 我以租戶身分設定 LLM Provider "openai" 顯示名稱 "OpenAI GPT"
    Then 回應狀態碼為 201
    And Provider 建立成功

    # Step 5: 驗證 Provider 已存在
    When 我查詢 Provider 列表
    Then 回應狀態碼為 200
    And Provider 列表包含 1 個項目
