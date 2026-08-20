Feature: Optimizer 與版本狀態機整合（Phase D）
  優化迴圈全程影子執行（不寫線上 bots 表）；
  產出走版本狀態機；rollback 收斂；run 端點 tenant scoping。

  Scenario: 受測對話帶 config_override 與 test_mode（影子執行）
    Given 一個 target_field 為 base_prompt 的影子 client 與候選 prompt "候選 A"
    When 透過影子 client 發送測試問題
    Then 底層 chat 收到 config_override 含 "候選 A" 且 test_mode 為 true

  Scenario: 候選 prompt 更新只寫記憶體不寫 DB
    Given 一個 target_field 為 base_prompt 的影子 client 與候選 prompt "候選 A"
    When 候選 prompt 更新為 "候選 B" 後再發送測試問題
    Then 底層 chat 收到 config_override 含 "候選 B"

  Scenario: 多輪題以 history_override 一次帶入（取代逐句 warm-up）
    Given 一個開啟 history_override 模式的 runner 與含兩則歷史的測試案例
    When runner 評估該案例
    Then 只發出一次 chat 且帶有兩則 history_override

  Scenario: 關閉 history_override 模式時維持逐句 warm-up（CLI 相容）
    Given 一個關閉 history_override 模式的 runner 與含兩則歷史的測試案例
    When runner 評估該案例
    Then 發出三次 chat 且未帶 history_override

  Scenario: 優化有進步時建立 optimizer draft 版本
    Given 一次 baseline 0.6 最佳 0.9 的優化結果
    When 執行優化收尾
    Then 建立一筆 source 為 optimizer 的 draft 且 source_run_id 為該 run
    And draft 的變更欄位包含 base_prompt

  Scenario: baseline 未進步時不建立版本
    Given 一次 baseline 與最佳同分的優化結果
    When 執行優化收尾
    Then 不建立任何版本

  Scenario: 建版失敗不影響 run 完成（fail-open）
    Given 一次有進步的優化結果但建版會拋錯
    When 執行優化收尾
    Then 收尾正常結束且無例外

  Scenario: rollback 收斂——gate 未啟用時建版並直接發布
    Given 一筆歷史 iteration 且 bot gate 未啟用
    When 對該 iteration 執行 rollback
    Then 建立 source 為 optimizer 的版本並已發布

  Scenario: rollback 收斂——gate 啟用時只建 draft 不發布
    Given 一筆歷史 iteration 且 bot gate 為 block
    When 對該 iteration 執行 rollback
    Then 建立 draft 且回報未發布（需走閘門）

  Scenario: rollback 跨租戶被拒
    Given 一筆屬於其他租戶的歷史 iteration
    When 對該 iteration 執行 rollback
    Then rollback 被拒絕（找不到 run）

  Scenario: GetRun 跨租戶被拒
    Given 一筆屬於其他租戶的歷史 iteration
    When 以本租戶查詢該 run
    Then 查詢被拒絕（找不到 run）
