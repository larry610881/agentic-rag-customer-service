Feature: 租戶端 Bot 變更紀錄可見性（Issue #71）
  bot 儲存已有稽核（操作者 / 前後設定），但只有 system_admin 的稽核頁看得到。
  tenant_admin 需要在 bot 頁看到「誰在何時改了哪些欄位」，且只能看自己租戶的 bot；
  跨租戶查詢視同不存在（404，不洩漏 bot 存在性）。

  Background:
    Given 機器人 "bot-001" 屬於租戶 "t-001"

  Scenario: tenant_admin 查看自己租戶 bot 的變更紀錄
    Given 稽核紀錄有一筆 "bot-001" 的 update，由使用者 "u-001" 將 "llm_model" 從 "gpt-4o" 改為 "gemini-3.7-flash"
    And 使用者 "u-001" 的 email 為 "admin@t-001.example"
    When 租戶 "t-001" 的 "tenant_admin" 查詢 "bot-001" 的變更紀錄
    Then 應回傳 1 筆紀錄
    And 第 1 筆紀錄的操作者 email 應為 "admin@t-001.example"
    And 第 1 筆紀錄應含欄位 "llm_model" 由 "gpt-4o" 變為 "gemini-3.7-flash"
    And 查詢條件應為 entity_type "bot" 且 entity_id "bot-001"，並聯集 parent "bot" "bot-001"

  Scenario: 跨租戶 tenant_admin 查詢視同不存在
    Given 稽核紀錄有一筆 "bot-001" 的 update，由使用者 "u-001" 將 "llm_model" 從 "gpt-4o" 改為 "gemini-3.7-flash"
    When 租戶 "t-002" 的 "tenant_admin" 查詢 "bot-001" 的變更紀錄
    Then 應拋出 EntityNotFoundError
    And 不應查詢稽核紀錄

  Scenario: system_admin 可查任意租戶的 bot 變更紀錄
    Given 稽核紀錄有一筆 "bot-001" 的 update，由使用者 "u-001" 將 "llm_model" 從 "gpt-4o" 改為 "gemini-3.7-flash"
    When 租戶 "system" 的 "system_admin" 查詢 "bot-001" 的變更紀錄
    Then 應回傳 1 筆紀錄

  Scenario: 查詢不存在的 bot 回傳 404
    When 租戶 "t-001" 的 "tenant_admin" 查詢 "bot-404" 的變更紀錄
    Then 應拋出 EntityNotFoundError

  Scenario: llm_params 巢狀欄位展平為 llm_params.<子欄位>
    Given 稽核紀錄有一筆 "bot-001" 的 update，llm_params 由 temperature 0.3、max_tokens 1024 改為 temperature 0.7、max_tokens 1024
    When 租戶 "t-001" 的 "tenant_admin" 查詢 "bot-001" 的變更紀錄
    Then 第 1 筆紀錄應含欄位 "llm_params.temperature" 由 "0.3" 變為 "0.7"
    And 第 1 筆紀錄不應含欄位 "llm_params.max_tokens"

  Scenario: 長文字欄位只回字數不回全文
    Given 稽核紀錄有一筆 "bot-001" 的 update，將 "bot_prompt" 從 20 字改為 140 字
    When 租戶 "t-001" 的 "tenant_admin" 查詢 "bot-001" 的變更紀錄
    Then 第 1 筆紀錄的欄位 "bot_prompt" 應只回 before_len 20、after_len 140
    And 第 1 筆紀錄的欄位 "bot_prompt" 不應含全文

  Scenario: 操作者查無使用者時 email 為空
    Given 稽核紀錄有一筆 "bot-001" 的 update，由使用者 "u-gone" 將 "name" 從 "A" 改為 "B"
    When 租戶 "t-001" 的 "tenant_admin" 查詢 "bot-001" 的變更紀錄
    Then 第 1 筆紀錄的操作者 email 應為空

  Scenario: 分頁：超過 limit 時回傳 next_cursor
    Given 稽核紀錄有 3 筆 "bot-001" 的 update
    When 租戶 "t-001" 的 "tenant_admin" 以 limit 2 查詢 "bot-001" 的變更紀錄
    Then 應回傳 2 筆紀錄
    And next_cursor 應指向第 2 筆紀錄

  Scenario: 分頁：未超過 limit 時 next_cursor 為空
    Given 稽核紀錄有一筆 "bot-001" 的 update，由使用者 "u-001" 將 "name" 從 "A" 改為 "B"
    When 租戶 "t-001" 的 "tenant_admin" 以 limit 2 查詢 "bot-001" 的變更紀錄
    Then 應回傳 1 筆紀錄
    And next_cursor 應為空

  Scenario: 分頁：帶 cursor 查詢時轉交 repository
    Given 稽核紀錄有一筆 "bot-001" 的 update，由使用者 "u-001" 將 "name" 從 "A" 改為 "B"
    When 租戶 "t-001" 的 "tenant_admin" 以 cursor "2026-09-07T00:00:00+00:00|log-9" 查詢 "bot-001" 的變更紀錄
    Then repository 應以 cursor "2026-09-07T00:00:00+00:00|log-9" 被呼叫

  # ── Issue #77：worker 稽核列連結所屬 bot，租戶端變更紀錄併入 ──

  Scenario: worker 建立時稽核列帶 tenant_id 與所屬 bot
    Given worker 用例已注入稽核紀錄器與 bot repository
    When 使用者 "u-001" 在 "bot-001" 建立 worker "門市"
    Then worker 稽核列的 tenant_id 應為 "t-001"
    And worker 稽核列的 parent 應為 "bot" "bot-001"
    And worker 稽核列的 action 應為 "create"

  Scenario: worker 更新與刪除時稽核列同樣帶 tenant_id 與所屬 bot
    Given worker 用例已注入稽核紀錄器與 bot repository
    When 使用者 "u-001" 在 "bot-001" 建立 worker "門市" 再改 prompt 為 "新版" 再刪除
    Then 每筆 worker 稽核列的 tenant_id 都應為 "t-001" 且 parent 為 "bot" "bot-001"
    And worker 稽核列的 action 依序為 "create", "update", "delete"

  Scenario: 租戶端 bot 變更紀錄併入 worker 列並附 worker 名稱
    Given 稽核紀錄有一筆 "bot-001" 的 update，由使用者 "u-001" 將 "llm_model" 從 "gpt-4o" 改為 "gemini-3.7-flash"
    And 稽核紀錄有一筆 worker "w-001"（屬 "bot-001"）的 update，將 "knowledge_base_ids" 從 "kb-a" 改為 "kb-b"
    And worker "w-001" 目前名稱為 "門市"
    When 租戶 "t-001" 的 "tenant_admin" 查詢 "bot-001" 的變更紀錄
    Then 應回傳 2 筆紀錄
    And 其中 entity_type "worker" 的紀錄 entity_name 應為 "門市"
    And 其中 entity_type "worker" 的紀錄應含欄位 "knowledge_base_ids" 由 "kb-a" 變為 "kb-b"
    And 其中 entity_type "bot" 的紀錄 entity_name 應為空

  Scenario: worker 已刪除時 entity_name 取稽核列快照中的名稱
    Given 稽核紀錄有一筆 worker "w-gone"（屬 "bot-001"）的 delete，快照名稱為 "退貨"
    When 租戶 "t-001" 的 "tenant_admin" 查詢 "bot-001" 的變更紀錄
    Then 其中 entity_type "worker" 的紀錄 entity_name 應為 "退貨"

  Scenario: worker_prompt 只回字數不回全文
    Given 稽核紀錄有一筆 worker "w-001"（屬 "bot-001"）的 update，將 "worker_prompt" 從 10 字改為 300 字
    When 租戶 "t-001" 的 "tenant_admin" 查詢 "bot-001" 的變更紀錄
    Then 第 1 筆紀錄的欄位 "worker_prompt" 應只回 before_len 10、after_len 300
    And 第 1 筆紀錄的欄位 "worker_prompt" 不應含全文
