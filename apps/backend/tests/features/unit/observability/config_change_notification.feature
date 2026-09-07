Feature: 設定變更通知（Issue #77）
  管理員（租戶或平台）改了 bot / worker / 租戶防護設定時，租戶可以選擇「哪些欄位群組
  變更要通知」（模型 / 提示詞 / 知識庫 / 工具 / 防護），通知走既有通知渠道
  （渠道需勾選「設定變更」）。通知失敗絕不能反過來讓儲存失敗（fail-open）。

  Background:
    Given 租戶 "t-001" 名稱為 "家樂福"
    And 使用者 "u-001" 的 email 為 "admin@t-001.example"，角色 "tenant_admin"

  # ── 欄位群組判定（domain） ──

  Scenario Outline: 變更欄位對應到欄位群組
    When 判定變更欄位 "<fields>" 所屬群組
    Then 觸及的群組應為 "<groups>"

    Examples:
      | fields                          | groups            |
      | llm_model                       | model             |
      | llm_params                      | model             |
      | bot_prompt                      | prompt            |
      | worker_prompt,name              | prompt            |
      | knowledge_base_ids              | knowledge         |
      | enabled_tools,max_tool_calls    | tools             |
      | guard_stages,output_format      | guard             |
      | llm_model,bot_prompt            | model,prompt      |
      | description,sort_order          |                   |

  # ── 派發 ──

  Scenario: 模型變更且租戶啟用「模型」群組時發送通知
    Given 租戶 "t-001" 未設定通知群組（採平台預設）
    And 有一個已啟用且勾選設定變更的通知渠道 "ops-teams"
    And 稽核事件："u-001" 將 "bot-001" 的 "llm_model" 從 "gpt-4o" 改為 "gemini-3.7-flash"
    And 機器人 "bot-001" 名稱為 "客服機器人"
    When 派發設定變更通知
    Then 渠道 "ops-teams" 應收到 1 則通知
    And 通知主旨應含 "客服機器人"
    And 通知內容應含 "admin@t-001.example"
    And 通知內容應含 "家樂福"
    And 通知內容應含 "gpt-4o" 與 "gemini-3.7-flash"

  Scenario: 只改描述時不發通知
    Given 租戶 "t-001" 未設定通知群組（採平台預設）
    And 有一個已啟用且勾選設定變更的通知渠道 "ops-teams"
    And 稽核事件："u-001" 將 "bot-001" 的 "description" 從 "舊" 改為 "新"
    When 派發設定變更通知
    Then 不應發送任何通知

  Scenario: 租戶關閉「模型」群組時模型變更不發通知
    Given 租戶 "t-001" 設定通知群組為 "prompt,knowledge"
    And 有一個已啟用且勾選設定變更的通知渠道 "ops-teams"
    And 稽核事件："u-001" 將 "bot-001" 的 "llm_model" 從 "gpt-4o" 改為 "gemini-3.7-flash"
    When 派發設定變更通知
    Then 不應發送任何通知

  Scenario: 租戶把群組設為空清單即完全關閉通知
    Given 租戶 "t-001" 設定通知群組為 ""
    And 有一個已啟用且勾選設定變更的通知渠道 "ops-teams"
    And 稽核事件："u-001" 將 "bot-001" 的 "bot_prompt" 從 "舊提示詞" 改為 "新提示詞"
    When 派發設定變更通知
    Then 不應發送任何通知

  Scenario: 平台（system_admin）對租戶的變更通知該租戶且操作者標「平台」
    Given 租戶 "t-001" 設定通知群組為 "guard"
    And 有一個已啟用且勾選設定變更的通知渠道 "ops-teams"
    And 平台稽核事件：對租戶 "t-001" 的防護設定將 "stages" 從 "regex_input" 改為 "regex_input,output_guard"
    When 派發設定變更通知
    Then 渠道 "ops-teams" 應收到 1 則通知
    And 通知內容應含 "平台"
    And 通知內容不應含 "admin@t-001.example"

  Scenario: worker 提示詞變更通知附 worker 名稱且只顯示字數
    Given 租戶 "t-001" 未設定通知群組（採平台預設）
    And 有一個已啟用且勾選設定變更的通知渠道 "ops-teams"
    And 稽核事件："u-001" 將 "bot-001" 底下 worker "w-001" 的 "worker_prompt" 從 10 字改為 300 字
    And worker "w-001" 名稱為 "門市"
    When 派發設定變更通知
    Then 渠道 "ops-teams" 應收到 1 則通知
    And 通知主旨應含 "門市"
    And 通知內容應含 "10 字" 與 "300 字"
    And 通知內容不應含全文 "xxxxxxxxxx"

  Scenario: 未勾選設定變更的渠道不收通知
    Given 租戶 "t-001" 未設定通知群組（採平台預設）
    And 有一個已啟用但未勾選設定變更的通知渠道 "ops-mail"
    And 有一個已啟用且勾選設定變更的通知渠道 "ops-teams"
    And 稽核事件："u-001" 將 "bot-001" 的 "llm_model" 從 "gpt-4o" 改為 "gemini-3.7-flash"
    When 派發設定變更通知
    Then 渠道 "ops-teams" 應收到 1 則通知
    And 渠道 "ops-mail" 不應收到通知

  Scenario: 非租戶範圍的稽核列不觸發通知
    Given 有一個已啟用且勾選設定變更的通知渠道 "ops-teams"
    And 稽核事件：平台 system prompt "default" 的 "base_prompt" 從 "a" 改為 "b"（無租戶）
    When 派發設定變更通知
    Then 不應發送任何通知

  # ── 稽核紀錄器掛勾：fail-open ──

  Scenario: 通知派發失敗不影響稽核與儲存
    Given 稽核紀錄器掛上會拋例外的通知掛勾
    When 稽核紀錄器記錄 "bot-001" 的 "llm_model" 從 "a" 改為 "b"
    Then 稽核列仍應寫入
    And 記錄呼叫不應拋出例外

  Scenario: 稽核寫入成功後才呼叫通知掛勾
    Given 稽核紀錄器掛上可觀察的通知掛勾
    When 稽核紀錄器記錄 "bot-001" 的 "llm_model" 從 "a" 改為 "b"
    Then 通知掛勾應收到該筆稽核列

  Scenario: 無變更時不呼叫通知掛勾
    Given 稽核紀錄器掛上可觀察的通知掛勾
    When 稽核紀錄器記錄 "bot-001" 的 "llm_model" 從 "a" 改為 "a"
    Then 通知掛勾不應被呼叫

  # ── 租戶通知偏好 ──

  Scenario: tenant_admin 設定自己租戶的通知群組並留下稽核
    Given 租戶 "t-001" 未設定通知群組（採平台預設）
    When 租戶 "t-001" 的 "tenant_admin" "u-001" 將租戶 "t-001" 的通知群組設為 "model,prompt,guard"
    Then 租戶 "t-001" 的通知群組應為 "model,prompt,guard"
    And 應寫入 entity_type "tenant_notification" 的 update 稽核，tenant_id 為 "t-001"

  Scenario: 通知群組設為 null 回到平台預設
    Given 租戶 "t-001" 設定通知群組為 "guard"
    When 租戶 "t-001" 的 "tenant_admin" "u-001" 將租戶 "t-001" 的通知群組設為 null
    Then 租戶 "t-001" 的通知群組應為平台預設 "model,prompt"

  Scenario: 跨租戶 tenant_admin 設定他租戶的通知群組被拒
    Given 租戶 "t-001" 未設定通知群組（採平台預設）
    When 租戶 "t-002" 的 "tenant_admin" "u-002" 將租戶 "t-001" 的通知群組設為 "model"
    Then 應拋出 PermissionError
    And 不應寫入任何稽核

  Scenario: system_admin 可設定任一租戶的通知群組
    Given 租戶 "t-001" 未設定通知群組（採平台預設）
    When 租戶 "system" 的 "system_admin" "u-sys" 將租戶 "t-001" 的通知群組設為 "knowledge"
    Then 租戶 "t-001" 的通知群組應為 "knowledge"

  Scenario: 未知群組名稱回 ValidationError
    Given 租戶 "t-001" 未設定通知群組（採平台預設）
    When 租戶 "t-001" 的 "tenant_admin" "u-001" 將租戶 "t-001" 的通知群組設為 "model,banana"
    Then 應拋出 ValidationError

  Scenario: 讀取通知偏好回傳目前設定與可選群組
    Given 租戶 "t-001" 設定通知群組為 "guard"
    When 讀取租戶 "t-001" 的通知偏好
    Then 通知偏好的 fields 應為 "guard"
    And 通知偏好的 available_groups 應含 "model", "prompt", "knowledge", "tools", "guard" 且各有標籤
