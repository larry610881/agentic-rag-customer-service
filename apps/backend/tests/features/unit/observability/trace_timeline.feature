Feature: Trace 時間軸儀表點 (Trace Timeline Instrumentation)
    身為維運
    我想要每個 trace 從請求邊界起算、含前置與收尾節點、檢索拆成子節點
    以便時間軸視圖能對帳到 100%，看出單一請求的時間分配

    Scenario: collector 以指定 t0 起算並包出 request 根節點
        Given 一個以 100 毫秒前為 t0 啟動的 trace
        And trace 內有一個無父節點的 "agent_llm" 節點
        When 呼叫 wrap_request
        Then trace 應有一個 node_type 為 "request" 且無父節點的根節點
        And 原本無父節點的 "agent_llm" 節點 parent_id 應指向根節點
        And 根節點 start_ms 應為 0 且 end_ms 至少 100

    Scenario Outline: web / widget 對話 trace 含請求邊界節點
        Given 一個有 2 則歷史訊息的既有對話與正常設定的 bot
        When 以來源 "<source>" 以非串流方式送出訊息並攔截 finish 的 trace
        Then trace 節點應依序包含 "conversation_load", "bot_load", "history_load", "persist"
        And trace 應有 "request" 根節點且 total_ms 等於根節點 end_ms
        And 所有非根節點的 parent_id 都不為 None

        Examples:
            | source |
            | web    |
            | widget |

    Scenario: web 串流對話 trace 同樣含請求邊界節點
        Given 一個有 2 則歷史訊息的既有對話與正常設定的 bot
        When 以串流方式送出訊息並攔截 finish 的 trace
        Then trace 節點應依序包含 "conversation_load", "bot_load", "history_load", "persist"
        And trace 應有 "request" 根節點且 total_ms 等於根節點 end_ms

    Scenario: LINE 對話 trace 從 webhook 收到時起算並含回覆推送節點
        Given Bot "shop-a" 設定了 LINE Channel 且 Agent 回覆 "30 天內可退貨"
        When 以 execute_for_bot 處理 LINE 文字事件並攔截 finish 的 trace
        Then trace 節點應依序包含 "bot_load", "webhook_verify", "conversation_load", "reply_push", "persist"
        And trace 應有 "request" 根節點且 total_ms 等於根節點 end_ms
        And 所有非根節點的 parent_id 都不為 None

    Scenario: RAG 檢索拆出 embed_query 與 vector_search 子節點
        Given 租戶 "T001" 的 KB "kb-1" 有 3 筆已 embed 的 chunks 且已啟動 trace
        When 執行 retrieve
        Then 應有 "embed_query" 與 "vector_search" 節點且 parent 為 "tool_result" 節點
        And "embed_query" 應在 "vector_search" 之前結束
