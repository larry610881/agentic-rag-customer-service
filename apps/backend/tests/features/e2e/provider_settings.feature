Feature: Provider Settings 管理流程
  E2E 驗證：建立 Provider → 查詢 → 更新 → 刪除

  Scenario: Provider 完整 CRUD 流程
    # Step 1: 建立 LLM Provider
    When 我建立 Provider 類型 "llm" 名稱 "openai" 顯示名稱 "OpenAI"
    Then 回應狀態碼為 201
    And Provider 名稱為 "openai"

    # Step 2: 建立 Embedding Provider
    When 我建立 Provider 類型 "embedding" 名稱 "qwen" 顯示名稱 "Qwen Embed"
    Then 回應狀態碼為 201

    # Step 3: 查詢全部
    When 我查詢所有 Provider
    Then 回應狀態碼為 200
    And Provider 列表有 2 個

    # Step 4: 按類型篩選
    When 我篩選類型 "llm" 的 Provider
    Then 回應狀態碼為 200
    And Provider 列表有 1 個

    # Step 5: 更新
    When 我更新第一個 Provider 顯示名稱為 "OpenAI GPT-4"
    Then 回應狀態碼為 200
    And 顯示名稱為 "OpenAI GPT-4"

    # Step 6: 刪除
    When 我刪除第一個 Provider
    Then 回應狀態碼為 204

    # Step 7: 確認已刪除
    When 我查詢所有 Provider
    Then Provider 列表有 1 個
