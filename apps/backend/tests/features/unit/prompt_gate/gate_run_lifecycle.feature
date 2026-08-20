Feature: Gate Run 生命週期與狀態機接線
  run: queued → running → completed/error；
  version: validating → pending_publish（過）/ draft（不過）；
  publish 依 gate_mode 分支；孤兒清理。

  Scenario: run 完成且通過 → 版本轉 pending_publish（定案 1=B 人工發布）
    Given 一個 validating 中的版本與其 gate run
    When gate run 以 PASS 完成
    Then run 狀態為 completed 且 verdict 為 pass
    And 版本狀態為 pending_publish 且 gate_verdict 為 pass

  Scenario: run 完成但未通過 → 版本退回 draft
    Given 一個 validating 中的版本與其 gate run
    When gate run 以 FAIL 完成（原因 hard_gate）
    Then run 狀態為 completed 且 verdict 為 fail
    And 版本狀態為 draft 且 gate_verdict 為 fail

  Scenario: 背景執行拋例外 → run 標 error、版本退回 draft（不卡死）
    Given 一個 validating 中的版本與其 gate run
    When gate run 執行中拋出例外
    Then run 狀態為 error
    And 版本狀態為 draft

  Scenario: pending_publish 版本人工發布成功
    Given 一個 pending_publish 且 verdict 為 pass 的版本
    When 發布該版本
    Then 版本狀態為 published 且 gate_verdict 為 pass

  Scenario: block 模式下驗證失敗的 draft 不可發布（409）
    Given bot gate_mode 為 block 且版本為 draft 且 gate_verdict 為 fail
    When 發布該版本
    Then 發布被拒絕（閘門未通過）

  Scenario: block 模式下 force 無效
    Given bot gate_mode 為 block 且版本為 draft 且 gate_verdict 為 fail
    When 以 force 發布該版本
    Then 發布被拒絕（閘門未通過）

  Scenario: warn 模式下驗證失敗可 force 發布（verdict=forced）
    Given bot gate_mode 為 warn 且版本為 draft 且 gate_verdict 為 fail
    When 以 force 發布該版本
    Then 版本狀態為 published 且 gate_verdict 為 forced

  Scenario: warn 模式下未帶 force 的失敗 draft 發布仍被拒（需顯式確認）
    Given bot gate_mode 為 warn 且版本為 draft 且 gate_verdict 為 fail
    When 發布該版本
    Then 發布被拒絕（閘門未通過）

  Scenario: 未驗證過的 draft 在 gate 啟用時發布被拒
    Given bot gate_mode 為 block 且版本為 draft 且從未驗證
    When 發布該版本
    Then 發布被拒絕（閘門未通過）

  Scenario: gate 未啟用時 draft 直接發布（Phase A 行為不變）
    Given bot gate_mode 為 off 且版本為 draft
    When 發布該版本
    Then 版本狀態為 published 且 gate_verdict 為 skipped

  Scenario: 孤兒清理——啟動時 running 的 run 標 error、validating 版本退 draft
    Given 一筆 running 中的 gate run 與其 validating 版本（模擬重啟遺留）
    When 執行孤兒清理
    Then run 狀態為 error
    And 版本狀態為 draft
