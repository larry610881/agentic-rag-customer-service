Feature: LINE Webhook 歷史上下文
    LINE webhook 在多輪對話時必須把 raw history 過 history_strategy 轉成
    history_context 字串，並透過 process_message 傳給 ReAct agent，
    否則 LLM 不會收到對話歷史 → 多輪代詞解析失效（regression: lost）。

    Scenario: 多輪對話 webhook 應傳非空 history_context 給 Agent
        Given 對話已有 4 條 user/assistant 訊息
        And LINE webhook bot 已注入 sliding window history_strategy
        When 系統處理新一輪 LINE 文字訊息
        Then Agent 應收到非空的 history_context
        And history_context 應包含先前訊息的內容

    Scenario: 首輪對話 webhook 應傳空 history_context 給 Agent
        Given 對話無任何先前訊息
        And LINE webhook bot 已注入 sliding window history_strategy
        When 系統處理新一輪 LINE 文字訊息
        Then Agent 應收到 history_context 為空字串
