Feature: 對話摘要排程條件 (Conversation Summary Policy)
    身為平台
    我想要對話摘要 cron 只處理達到最少訊息數的對話
    以便一兩輪就結束的客服對話不再各耗 1 次 LLM + 1 次 embedding

    Scenario: 掃描時帶入最少訊息數門檻
        Given 設定 conversation_summary_min_messages 為 6
        When worker 執行 conversation_summary_scan_task
        Then find_pending_summary 應以 min_message_count=6 被呼叫
