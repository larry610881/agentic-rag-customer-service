Feature: Eval Token 用量分流
  eval_gate / prompt_optimize / playground 三分類獨立記帳、run_id 歸因、
  header 標記解析 fail-open、mutator 記帳不影響優化主流程。

  Scenario: 新分類記帳並歸因 run_id
    When 以 request_type "prompt_optimize" 與 run_id "run-1" 記帳 1000 tokens
    Then 帳本寫入一筆 request_type 為 "prompt_optimize" 的記錄
    And 該筆記錄的 run_id 為 "run-1"

  Scenario: config_version_id 歸因欄位可寫入
    When 以 request_type "chat_web" 與 config_version_id "ver-9" 記帳 500 tokens
    Then 該筆記錄的 config_version_id 為 "ver-9"

  Scenario: 非法分類仍被白名單拒絕
    When 以不合法 request_type "not_a_category" 記帳 100 tokens
    Then 記帳被拒絕（ValueError）

  Scenario: admin 帶合法 eval header 解析為對應分類
    When 以角色 "tenant_admin" 解析 header 分類 "eval_gate" 與 run_id "run-2"
    Then 解析結果 request_type 為 "eval_gate" 且 run_id 為 "run-2"

  Scenario: 無 header 時維持 chat_web
    When 以角色 "tenant_admin" 解析空 header
    Then 解析結果 request_type 為 "chat_web" 且無 run_id

  Scenario: header 分類不在 eval 白名單時 fallback chat_web
    When 以角色 "system_admin" 解析 header 分類 "chat_line" 與 run_id "run-3"
    Then 解析結果 request_type 為 "chat_web" 且無 run_id

  Scenario: 角色不足時 fallback chat_web（header 可偽造、role 不可）
    When 以角色 "user" 解析 header 分類 "eval_gate" 與 run_id "run-4"
    Then 解析結果 request_type 為 "chat_web" 且無 run_id

  Scenario: mutator 記帳回呼被呼叫且攜帶 usage_metadata
    Given 一個 LLM 回傳固定內容與 usage_metadata 的 PromptMutator
    When 執行一次 mutate
    Then usage 回呼收到 model 名稱與 input/output tokens

  Scenario: mutator 記帳回呼失敗不影響優化主流程（fail-open）
    Given 一個 usage 回呼必定拋錯的 PromptMutator
    When 執行一次 mutate
    Then mutate 仍回傳改寫後的 prompt
