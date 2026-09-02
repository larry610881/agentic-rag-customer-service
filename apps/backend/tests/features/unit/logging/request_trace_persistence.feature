Feature: 請求 SQL trace 的持久化閘控 (Request Trace Persistence)
    身為維運
    我想要 TRACE_THRESHOLD_MS 真正決定 trace_steps 是否寫入 request_logs
    以便一般請求不再把每一條 SQL 片段塞進 DB

    Scenario: 門檻為 0 時不持久化 trace_steps
        Given trace 門檻為 0 毫秒
        And 請求期間記錄了 3 個 trace 步驟
        When 以請求耗時 50 毫秒 flush trace
        Then flush 結果應為 None

    Scenario: 請求耗時未達門檻時不持久化
        Given trace 門檻為 1000 毫秒
        And 請求期間記錄了 3 個 trace 步驟
        When 以請求耗時 500 毫秒 flush trace
        Then flush 結果應為 None

    Scenario: 請求耗時達門檻時持久化
        Given trace 門檻為 1000 毫秒
        And 請求期間記錄了 3 個 trace 步驟
        When 以請求耗時 1500 毫秒 flush trace
        Then flush 結果應含 3 個步驟
