Feature: 真實流量回放 pairwise 對比（Phase G，spec §14 層次 2）
  抽最近 N 則真實使用者問題，新舊兩版設定影子執行，
  LLM judge 換位雙判（防 position bias），一致才計勝負。

  Scenario: 換位判定一致 → 計入勝負（candidate 勝）
    When 正序判定為 "2" 且換位判定為 "1"
    Then 該題結果為 candidate

  Scenario: 換位判定一致 → 計入勝負（baseline 勝）
    When 正序判定為 "1" 且換位判定為 "2"
    Then 該題結果為 baseline

  Scenario: 換位判定不一致 → 平手（position bias 防護）
    When 正序判定為 "1" 且換位判定為 "1"
    Then 該題結果為 tie

  Scenario: 任一判定為平手 → 平手
    When 正序判定為 "平手" 且換位判定為 "2"
    Then 該題結果為 tie

  Scenario: 聚合統計勝負與勝率
    Given 逐題結果為 candidate, candidate, baseline, tie
    When 聚合回放結果
    Then 統計為 candidate 2 勝 baseline 1 勝 1 平且勝率 0.5

  Scenario: 無真實歷史訊息時啟動被拒（422）
    Given 一個沒有任何歷史使用者訊息的 bot
    When 啟動回放對比
    Then 啟動被拒絕且錯誤類型為 no_history

  Scenario: 回放共用每日驗證限額
    Given 一個當日已達 gate_daily_limit 的 bot
    When 啟動回放對比
    Then 啟動被拒絕且錯誤類型為 daily_limit_exceeded

  Scenario: 回放完成 → run 記 replay_compare 明細且逐題並排
    Given 一個有兩則歷史問題的 bot 與 candidate 版本
    When 執行回放對比背景任務
    Then run 完成且 details 型別為 replay_compare
    And 每題含 baseline 與 candidate 的回應與判定

  Scenario: judge 失敗的題目記為 tie（fail-open）
    Given 一個有兩則歷史問題的 bot 且 judge 會拋錯
    When 執行回放對比背景任務
    Then run 完成且全部題目判定為 tie
