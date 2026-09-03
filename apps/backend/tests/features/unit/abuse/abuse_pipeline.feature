Feature: 異常控管三通路接線 (Abuse Control Pipeline Wiring)
    身為對外 AI 客服的維運者
    我要 web / widget / API 與 LINE 兩條管線、rate limiter 都接同一個 AbuseControlService
    以便同一個主體在任何通路的行為一致，且回應不洩漏偵測原因

    # --- web / widget / API：SendMessageUseCase ---

    Scenario: L2 主體送訊息只回固定文案，不進 LLM
        Given 接了異常控管的 SendMessageUseCase
        And 訪客 "v1" 已被鎖定在等級 2
        When 訪客 "v1" 送出訊息
        Then 回覆為 "請稍後再試"
        And agent 未被呼叫

    Scenario: L3 主體送訊息被拒（429 語意）
        Given 接了異常控管的 SendMessageUseCase
        And 訪客 "v1" 已被鎖定在等級 3
        When 訪客 "v1" 送出訊息
        Then 應拋出 AbuseBlockedError 且 retry_after 大於 0
        And agent 未被呼叫

    Scenario: L1 主體進入保守模式：不呼叫工具、加婉拒指令
        Given 接了異常控管的 SendMessageUseCase
        And 訪客 "v1" 已被鎖定在等級 1
        When 訪客 "v1" 送出訊息
        Then agent 被呼叫且 enabled_tools 為空、system_prompt 含保守指令
        And trace 的 abuse_level 為 1

    Scenario: Guard 命中會計分
        Given 接了異常控管的 SendMessageUseCase
        And 這回合 Guard 會命中
        When 訪客 "v1" 送出訊息
        Then 訪客 "v1" 的異常分數為 5

    Scenario: 沒有主體的請求不計分也不受控
        Given 接了異常控管的 SendMessageUseCase
        And 訪客 "v1" 已被鎖定在等級 3
        When 無主體送出訊息
        Then agent 被呼叫

    Scenario: 串流 preflight 在 L3 時拋出 AbuseBlockedError
        Given 接了異常控管的 SendMessageUseCase
        And 訪客 "v1" 已被鎖定在等級 3
        When 訪客 "v1" 的串流 preflight
        Then 應拋出 AbuseBlockedError 且 retry_after 大於 0

    # --- LINE：HandleWebhookUseCase ---

    Scenario: LINE 使用者在 L3 只收到固定文案，agent 不被呼叫
        Given 接了異常控管的 LINE webhook use case
        And LINE 使用者 "U123" 已被鎖定在等級 3
        When LINE 使用者 "U123" 送出訊息
        Then LINE 回覆為 "AI 助手暫時休息，請稍後再試"
        And LINE agent 未被呼叫

    Scenario: LINE 使用者在 L2 只收到固定文案
        Given 接了異常控管的 LINE webhook use case
        And LINE 使用者 "U123" 已被鎖定在等級 2
        When LINE 使用者 "U123" 送出訊息
        Then LINE 回覆為 "請稍後再試"
        And LINE agent 未被呼叫

    Scenario: LINE Guard 命中會計分
        Given 接了異常控管的 LINE webhook use case
        And LINE 這回合 Guard 會命中
        When LINE 使用者 "U123" 送出訊息
        Then LINE 使用者 "U123" 的異常分數為 5

    # --- HTTP 契約 ---

    Scenario Outline: 被拒時回 429，body 只有 temporarily_unavailable 與 retry_after
        Given 已啟動的異常控管 HTTP 測試應用
        When 以會被拒的主體請求 "<path>"
        Then HTTP 狀態碼為 429
        And body 為 temporarily_unavailable 且 retry_after 為 600，不含原因
        And 回應標頭 Retry-After 為 "600"

        Examples:
            | path                       |
            | /api/v1/agent/chat         |
            | /api/v1/agent/chat/stream  |

    # --- rate limiter ---

    Scenario: L2 主體的每分鐘上限被壓到 5
        Given 掛了異常控管的限流中介層
        And 訪客 "v1" 已被鎖定在等級 2
        When 訪客 "v1" 持 widget 票請求聊天端點
        Then 限流檢查包含 abuse key 且上限為 5

    Scenario: 未受控主體不加額外限流
        Given 掛了異常控管的限流中介層
        When 訪客 "v1" 持 widget 票請求聊天端點
        Then 限流檢查不含 abuse key
