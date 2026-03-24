Feature: Karpathy Loop Runner
  自動化 prompt 優化迴圈

  Scenario: 正常完成優化迴圈
    Given 一個 dataset 和初始 prompt
    And mutator 會產出改進的 prompt
    And 評估分數持續提升
    When 我執行優化迴圈 最多 5 輪
    Then 最終 prompt 應是分數最高的版本
    And 迭代次數應大於 1

  Scenario: Patience 機制觸發 early stop
    Given 一個 dataset 和初始 prompt
    And 分數連續 3 輪未改善
    When 我執行優化迴圈 patience 為 3
    Then 應提前停止
    And 最終 prompt 應是最佳版本

  Scenario: Budget 上限停止
    Given 一個 dataset 和初始 prompt 含 3 個 cases
    When 我執行優化迴圈 budget 為 6
    Then 應在 budget 耗盡後停止

  Scenario: Dry run 只評估不變更
    Given 一個 dataset 和初始 prompt
    When 我以 dry_run 模式執行
    Then 只回傳 baseline 評估結果
    And prompt 不應被修改
