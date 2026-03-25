Feature: Evaluator
  評估引擎：跑 binary assertions 並計算分數

  Scenario: 所有 assertions 通過
    Given 一個包含 3 個 test cases 的 dataset
    And 所有 API 回應都正確
    When 我執行評估
    Then quality_score 應為 1.0
    And 所有 case 都應通過

  Scenario: P0 hard-fail — P0 assertion 失敗則 case_score 為 0
    Given 一個包含 P0 assertion 的 test case
    And P0 assertion 失敗
    When 我執行評估
    Then 該 case 的 score 應為 0.0
    And overall quality_score 應低於 1.0

  Scenario: 混合 P0/P1/P2 加權評分
    Given 一個包含 P0 P1 P2 各一個 case 的 dataset
    And P1 case 部分通過
    When 我執行評估
    Then quality_score 應根據優先權加權計算

  Scenario: 成本感知評分
    Given 一個包含 cost_config 的 dataset
    And API 回應含 usage 資訊
    When 我執行評估
    Then final_score 應結合 quality 和 cost 分數

  Scenario: 空回應處理
    Given 一個 test case
    And API 回應為空字串
    When 我執行評估
    Then 該 case 應標記為 api_error 且 score 為 0
