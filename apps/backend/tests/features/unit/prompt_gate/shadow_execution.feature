Feature: Config Override 影子執行與 test-mode 隔離
  draft 快照 overlay 到真實管線；測試對話六面隔離
  （對話不落庫、guard 攔截分支也不落庫、不 memory、不線上 eval、
  trace 不落庫但回傳 nodes、guard 照跑）。

  Scenario: config_override 以 overlay 生效
    Given 一個 base_prompt 為 "線上提示詞" 的 bot 與含 "草稿提示詞" 的 override 快照
    When 以 config_override 執行影子對話
    Then agent 收到的 system prompt 含 "草稿提示詞"
    And bot repository 未被呼叫 save

  Scenario: override 不能繞過租戶隔離
    Given 一個屬於其他租戶的 bot
    When 以 config_override 執行影子對話
    Then 執行被拒絕（找不到 bot）

  Scenario: test_mode 不寫對話與訊息
    Given 一個正常設定的 bot
    When 以 test_mode 執行影子對話
    Then conversation repository 未被呼叫 save

  Scenario: test_mode 下 guard 攔截分支也不落庫
    Given 一個正常設定的 bot 且 guard 會攔截輸入
    When 以 test_mode 執行影子對話
    Then 回應為 guard 攔截訊息
    And conversation repository 未被呼叫 save

  Scenario: test_mode 不觸發 memory extraction 與線上 eval
    Given 一個開啟 memory 與 eval_depth 的 bot
    When 以 test_mode 執行影子對話
    Then 未 enqueue extract_memory 與 run_evaluation

  Scenario: test_mode 的 trace 不落庫但回傳 compact nodes
    Given 一個正常設定的 bot
    When 以 test_mode 執行影子對話
    Then 回應含 trace_id 與 trace_nodes
    And trace 未被持久化

  Scenario: history_override 取代 DB 歷史
    Given 一個正常設定的 bot 與兩則 history_override 訊息
    When 以 test_mode 與 history_override 執行影子對話
    Then agent 收到的對話歷史即為 override 內容
    And conversation repository 未被查詢歷史
