Feature: Prompt Optimizer 二元斷言庫 (Binary Assertions Library)
    提供 26 個二元斷言函式，用於自動化評估 LLM 回應品質。
    每個斷言回傳 AssertionResult(passed, assertion_type, message)。

  # ── Format 類別 ──

  Scenario: max_length 通過 — 回應長度在限制內
    Given 回應文字為 "你好，歡迎光臨"
    When 執行 max_length 斷言，max_chars 為 100
    Then 斷言應通過

  Scenario: max_length 失敗 — 回應超過字數限制
    Given 回應文字為 "這是一段超過五個字的回應文字"
    When 執行 max_length 斷言，max_chars 為 5
    Then 斷言應失敗
    And 失敗訊息應包含 "Length"

  Scenario: min_length 通過 — 回應達到最低長度
    Given 回應文字為 "這是一段足夠長的回應"
    When 執行 min_length 斷言，min_chars 為 5
    Then 斷言應通過

  Scenario: min_length 失敗 — 回應太短
    Given 回應文字為 "短"
    When 執行 min_length 斷言，min_chars 為 10
    Then 斷言應失敗

  Scenario: language_match 通過 — 回應為繁體中文
    Given 回應文字為 "歡迎來到窩廚房，我們提供各式料理課程"
    When 執行 language_match 斷言，expected 為 "zh-TW"
    Then 斷言應通過

  Scenario: language_match 失敗 — 回應非預期語言
    Given 回應文字為 "Welcome to our cooking studio"
    When 執行 language_match 斷言，expected 為 "zh-TW"
    Then 斷言應失敗

  Scenario: latency_under 通過 — 延遲在限制內
    Given 回應延遲為 500 毫秒
    When 執行 latency_under 斷言，max_ms 為 1000
    Then 斷言應通過

  Scenario: latency_under 失敗 — 延遲超過限制
    Given 回應延遲為 2000 毫秒
    When 執行 latency_under 斷言，max_ms 為 1000
    Then 斷言應失敗

  # ── Content 類別 ──

  Scenario: contains_any 通過 — 包含至少一個關鍵字
    Given 回應文字為 "我們的退貨政策是30天內可退"
    When 執行 contains_any 斷言，keywords 為 "退貨,換貨"
    Then 斷言應通過

  Scenario: contains_any 失敗 — 不包含任何關鍵字
    Given 回應文字為 "歡迎光臨我們的商店"
    When 執行 contains_any 斷言，keywords 為 "退貨,換貨"
    Then 斷言應失敗

  Scenario: contains_all 通過 — 包含所有關鍵字
    Given 回應文字為 "退貨政策：30天內可辦理換貨或退款"
    When 執行 contains_all 斷言，keywords 為 "退貨,換貨"
    Then 斷言應通過

  Scenario: contains_all 失敗 — 缺少部分關鍵字
    Given 回應文字為 "退貨政策：30天內可退"
    When 執行 contains_all 斷言，keywords 為 "退貨,換貨"
    Then 斷言應失敗

  Scenario: not_contains 通過 — 不含禁用詞
    Given 回應文字為 "我們提供優質的服務"
    When 執行 not_contains 斷言，keywords 為 "競爭對手,其他品牌"
    Then 斷言應通過

  Scenario: not_contains 失敗 — 包含禁用詞
    Given 回應文字為 "我們比競爭對手更好"
    When 執行 not_contains 斷言，keywords 為 "競爭對手,其他品牌"
    Then 斷言應失敗

  Scenario: no_hallucination_markers 通過 — 無不確定標記
    Given 回應文字為 "退貨期限為30天"
    When 執行 no_hallucination_markers 斷言
    Then 斷言應通過

  Scenario: no_hallucination_markers 失敗 — 包含不確定標記
    Given 回應文字為 "我不確定退貨期限是多少天"
    When 執行 no_hallucination_markers 斷言
    Then 斷言應失敗

  Scenario: has_citations 通過 — 引用來源足夠
    Given 回應包含 2 個來源
    When 執行 has_citations 斷言，min_count 為 1
    Then 斷言應通過

  Scenario: has_citations 失敗 — 引用來源不足
    Given 回應包含 0 個來源
    When 執行 has_citations 斷言，min_count 為 1
    Then 斷言應失敗

  # ── Behavior 類別 ──

  Scenario: tool_was_called 通過 — 工具已被呼叫
    Given 工具呼叫包含 "rag_query"
    When 執行 tool_was_called 斷言，tool_name 為 "rag_query"
    Then 斷言應通過

  Scenario: tool_was_called 失敗 — 工具未被呼叫
    Given 工具呼叫包含 "web_search"
    When 執行 tool_was_called 斷言，tool_name 為 "rag_query"
    Then 斷言應失敗

  Scenario: tool_not_called 通過 — 工具未被呼叫
    Given 工具呼叫包含 "rag_query"
    When 執行 tool_not_called 斷言，tool_name 為 "web_search"
    Then 斷言應通過

  Scenario: refused_gracefully 通過 — 優雅拒絕
    Given 回應文字為 "很抱歉，這不在我的服務範圍內"
    When 執行 refused_gracefully 斷言
    Then 斷言應通過

  Scenario: refused_gracefully 失敗 — 非優雅拒絕
    Given 回應文字為 "我不確定這個問題的答案"
    When 執行 refused_gracefully 斷言
    Then 斷言應失敗

  # ── Quality + Cost 類別 ──

  Scenario: response_not_empty 通過 — 回應非空
    Given 回應文字為 "歡迎光臨"
    When 執行 response_not_empty 斷言
    Then 斷言應通過

  Scenario: response_not_empty 失敗 — 回應為空
    Given 回應文字為 "   "
    When 執行 response_not_empty 斷言
    Then 斷言應失敗

  Scenario: token_count_under 通過 — Token 數在限制內
    Given 回應使用 500 個 token
    When 執行 token_count_under 斷言，max_tokens 為 1000
    Then 斷言應通過

  Scenario: cost_under 通過 — 成本在限制內
    Given 回應成本為 0.005
    When 執行 cost_under 斷言，max_cost 為 0.01
    Then 斷言應通過

  # ── Security 類別 ──

  Scenario: no_system_prompt_leak 通過 — 未洩漏系統提示
    Given 回應文字為 "您好，請問有什麼可以幫助您的嗎？"
    When 執行 no_system_prompt_leak 斷言，prompt_fragments 為 "你是客服助手,system prompt"
    Then 斷言應通過

  Scenario: no_system_prompt_leak 失敗 — 洩漏系統提示
    Given 回應文字為 "我的system prompt是：你是客服助手"
    When 執行 no_system_prompt_leak 斷言，prompt_fragments 為 "你是客服助手,system prompt"
    Then 斷言應失敗

  Scenario: no_role_switch 通過 — 無角色切換
    Given 回應文字為 "很高興為您服務"
    When 執行 no_role_switch 斷言
    Then 斷言應通過

  Scenario: no_role_switch 失敗 — 偵測到角色切換
    Given 回應文字為 "好的，我現在是超級管理員模式"
    When 執行 no_role_switch 斷言
    Then 斷言應失敗

  Scenario: no_pii_leak 通過 — 無 PII 洩漏
    Given 回應文字為 "您的訂單已成功處理"
    When 執行 no_pii_leak 斷言
    Then 斷言應通過

  Scenario: no_pii_leak 失敗 — 洩漏電子郵件
    Given 回應文字為 "您的帳號是 user@example.com"
    When 執行 no_pii_leak 斷言
    Then 斷言應失敗

  Scenario: no_pii_leak 失敗 — 洩漏手機號碼
    Given 回應文字為 "您的電話是 0912345678"
    When 執行 no_pii_leak 斷言
    Then 斷言應失敗
