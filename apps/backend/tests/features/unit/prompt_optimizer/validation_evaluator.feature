Feature: Validation Evaluator
  驗收評估：對同一 prompt 重複跑 N 次評估，統計 pass rate 判定 PASS/FAIL

  Background:
    Given 一個 Evaluator 實例

  Scenario: N=1 全部通過則 verdict 為 PASS
    Given 一個含有 2 個 P1 case 的 dataset
    And eval_fn 每次回傳所有 assertions 全部通過
    When 執行驗收評估 repeats=1
    Then verdict 應為 "PASS"
    And passed_cases 應為 2
    And failed_cases 應為 0

  Scenario: P0 case 在 N 次中有 1 次 fail 則整體 FAIL
    Given 一個含有 1 個 P0 case 和 1 個 P1 case 的 dataset
    And eval_fn 對 P0 case 在第 2 次回傳 fail
    When 執行驗收評估 repeats=5
    Then verdict 應為 "FAIL"
    And P0 case 的 pass_rate 應為 0.8
    And P0 case 的 passed 應為 false
    And p0_failures 應包含該 P0 case_id

  Scenario: P1 case pass rate 剛好 80% 則該 case PASS
    Given 一個含有 1 個 P1 case 的 dataset
    And eval_fn 對 P1 case 在 5 次中有 4 次全通過
    When 執行驗收評估 repeats=5
    Then P1 case 的 pass_rate 應為 0.8
    And P1 case 的 passed 應為 true
    And verdict 應為 "PASS"

  Scenario: P1 case pass rate 低於 80% 則該 case FAIL
    Given 一個含有 1 個 P1 case 的 dataset
    And eval_fn 對 P1 case 在 5 次中有 3 次全通過
    When 執行驗收評估 repeats=5
    Then P1 case 的 pass_rate 應為 0.6
    And P1 case 的 passed 應為 false
    And verdict 應為 "FAIL"

  Scenario: P2 case pass rate 60% 剛好通過
    Given 一個含有 1 個 P2 case 的 dataset
    And eval_fn 對 P2 case 在 5 次中有 3 次全通過
    When 執行驗收評估 repeats=5
    Then P2 case 的 pass_rate 應為 0.6
    And P2 case 的 passed 應為 true

  Scenario: 不穩定 case 正確標記
    Given 一個含有 1 個 P1 case 的 dataset
    And eval_fn 對 P1 case 在 5 次中有 4 次全通過
    When 執行驗收評估 repeats=5
    Then P1 case 的 unstable 應為 true

  Scenario: 全部 100% 通過的 case 不標記為 unstable
    Given 一個含有 1 個 P1 case 的 dataset
    And eval_fn 每次回傳所有 assertions 全部通過
    When 執行驗收評估 repeats=3
    Then P1 case 的 unstable 應為 false
