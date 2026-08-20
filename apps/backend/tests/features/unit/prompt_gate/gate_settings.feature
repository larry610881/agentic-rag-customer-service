Feature: 閘門三層開關與前置條件
  平台 per-tenant flag → bot gate_mode → 綁題集前置條件；
  日限額與値域驗證。

  Scenario: 租戶 flag 未開時 StartGateRun 被拒（403）
    Given 租戶未開啟 prompt_gate 且 bot gate_mode 為 block 並已綁題集
    When 對 draft 版本啟動 gate run
    Then 啟動被拒絕且錯誤類型為 gate_not_enabled

  Scenario: bot gate_mode 為 off 時 StartGateRun 被拒（409）
    Given 租戶已開啟 prompt_gate 且 bot gate_mode 為 off
    When 對 draft 版本啟動 gate run
    Then 啟動被拒絕且錯誤類型為 gate_mode_off

  Scenario: 未綁自訂題集時 StartGateRun 被拒（422）
    Given 租戶已開啟 prompt_gate 且 bot gate_mode 為 block 但未綁任何題集
    When 對 draft 版本啟動 gate run
    Then 啟動被拒絕且錯誤類型為 no_dataset_bound

  Scenario: 自訂集存在但全部 case 停用時視同未綁
    Given 租戶已開啟 prompt_gate 且 bot 綁的自訂集全部 case 停用
    When 對 draft 版本啟動 gate run
    Then 啟動被拒絕且錯誤類型為 no_dataset_bound

  Scenario: 平台通用集不算數（避免空殼啟用）
    Given 租戶已開啟 prompt_gate 且只有平台通用集含啟用案例
    When 對 draft 版本啟動 gate run
    Then 啟動被拒絕且錯誤類型為 no_dataset_bound

  Scenario: 當日次數達 gate_daily_limit 時被拒（429）
    Given 租戶已開啟 prompt_gate 且 bot 已綁題集且當日已跑 20 次
    When 對 draft 版本啟動 gate run
    Then 啟動被拒絕且錯誤類型為 daily_limit_exceeded

  Scenario: 估算成本超過 gate_budget_usd 直接擋（422）
    Given 租戶已開啟 prompt_gate 且 bot 已綁題集且估算成本超過預算
    When 對 draft 版本啟動 gate run
    Then 啟動被拒絕且錯誤類型為 budget_exceeded

  Scenario: 前置全過時啟動成功並轉 validating
    Given 租戶已開啟 prompt_gate 且 bot 已綁題集且前置全過
    When 對 draft 版本啟動 gate run
    Then 回傳 run_id 且版本狀態為 validating

  Scenario: bot 勾選排除的平台題不進題集且留下審計清單
    Given 平台通用集有三題且 bot 排除了其中一題
    When 收集 gate run 題集
    Then 題集含兩題平台題且排除清單記錄該題
    And 自訂集題目不受排除影響

  Scenario: 排除只施於平台集，相同 id 出現在自訂集不受影響
    Given 自訂集有一題其 id 被列在排除清單
    When 收集 gate run 題集
    Then 該自訂題仍在題集內

  Scenario: UpdateBot 將 gate_mode 設為 block 但未綁題集被拒
    Given 一個未綁任何題集的 bot
    When 透過 UpdateBot 將 gate_mode 改為 block
    Then 更新被拒絕且錯誤訊息含 "須先設定問題集"

  Scenario: UpdateBot 已綁題集時可啟用 gate_mode
    Given 一個已綁題集（含啟用案例）的 bot
    When 透過 UpdateBot 將 gate_mode 改為 warn
    Then 更新成功且 gate_mode 為 warn
