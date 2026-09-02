Feature: 線上 LLM 自評下線 (Online Eval Retired)
    身為平台
    我決定線上每輪 LLM 自評下線（品質驗收改依 prompt gate 離線回放與真實回饋）
    以便每輪對話不再排入從未成功執行的 run_evaluation 任務

    Scenario: 非串流對話不 enqueue run_evaluation
        Given 一個 eval_depth 為 "L1" 的 bot
        When 以非串流方式送出訊息
        Then 不應 enqueue 任何 "run_evaluation" 任務

    Scenario: 串流對話不 enqueue run_evaluation
        Given 一個 eval_depth 為 "L1" 的 bot
        When 以串流方式送出訊息
        Then 不應 enqueue 任何 "run_evaluation" 任務

    Scenario: Bot 預設 eval_depth 為 off
        When 建立一個未指定 eval_depth 的 Bot 實體
        Then 該 Bot 的 eval_depth 應為 "off"

    Scenario: worker 不再註冊 run_evaluation 任務
        When 讀取 worker 的任務註冊表
        Then 註冊表不應包含 "run_evaluation"
