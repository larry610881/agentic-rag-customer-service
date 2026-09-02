Feature: 輔助 LLM 呼叫記帳 (Auxiliary LLM Usage Accounting)
    身為平台
    我想要 query rewrite、HyDE、記憶萃取、歷史摘要的 LLM 呼叫都寫入 token_usage_records 與 trace
    以便開啟這些功能的 bot 成本不被低估

    Scenario: query rewrite 記帳並產生 trace 節點
        Given call_llm 回傳文字 "改寫後查詢" 且 input 120 output 8 tokens
        And 已注入 record_usage
        When 以 tenant "tenant-001" 執行 rewrite_query
        Then 應以 request_type "query_rewrite" 記錄 tenant "tenant-001" 的用量 input 120 output 8
        And 應新增 label 為 "query_rewrite" 的 trace 節點

    Scenario: HyDE 記帳並產生 trace 節點
        Given call_llm 回傳文字 "假設答案" 且 input 150 output 40 tokens
        And 已注入 record_usage
        When 以 tenant "tenant-001" 執行 generate_hyde
        Then 應以 request_type "hyde" 記錄 tenant "tenant-001" 的用量 input 150 output 40
        And 應新增 label 為 "hyde" 的 trace 節點

    Scenario: 未注入 record_usage 時 rewrite 行為不變
        Given call_llm 回傳文字 "改寫後查詢" 且 input 120 output 8 tokens
        When 以 tenant "tenant-001" 執行 rewrite_query
        Then rewrite 結果應為 "改寫後查詢"

    Scenario: 記憶萃取以正確簽名呼叫 LLM 並回傳用量
        Given LLMService.generate 回傳 JSON 事實陣列且 input 300 output 50 tokens
        When 執行記憶萃取並帶 usage_collector
        Then 應以 system_prompt 與 user_message 關鍵字參數呼叫 generate
        And 萃取結果應含 1 筆事實
        And usage_collector 應含 input 300 output 50

    Scenario: 記憶萃取用例記帳
        Given 萃取服務回傳 1 筆事實並回填 usage input 300 output 50
        And 記憶萃取用例已注入 record_usage
        When 以 tenant "tenant-001" 執行記憶萃取用例
        Then 應以 request_type "memory_extraction" 記錄 tenant "tenant-001" 的用量 input 300 output 50

    Scenario: summary_recent 歷史摘要記帳
        Given summary_recent 策略已注入 record_usage 且 LLM 回傳摘要 input 400 output 60
        When 以 tenant "tenant-001" 對 8 則訊息執行 summary_recent
        Then 應以 request_type "history_summary" 記錄 tenant "tenant-001" 的用量 input 400 output 60
