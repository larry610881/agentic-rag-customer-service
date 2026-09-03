Feature: 快速道 profile — bot mode 與 worker 覆寫 (Fast Lane Profile)
    身為平台
    我想要 bot 層級的 mode（fast / deep）決定預設行為，worker 的 direct_retrieval 作個別覆寫
    以便快速道 bot 不用逐個 worker 設定，且升級 ReAct 時有上限、不付額外 LLM

    Scenario: fast bot 沒有 worker 也走快速道
        Given 一個 mode 為 "fast" 且沒有 worker 的 bot，檢索分數 0.85
        When 以 web 送出訊息
        Then Agent 應以 max_tool_calls 1 被呼叫
        And 共用檢索應被呼叫 1 次

    Scenario: fast bot 檢索未過門檻 — 升級 ReAct 但工具呼叫上限 2
        Given 一個 mode 為 "fast" 且沒有 worker 的 bot，檢索分數 0.10
        When 以 web 送出訊息
        Then Agent 應以 max_tool_calls 2 被呼叫

    Scenario: fast bot 即使 bot 開了 rerank，快速道檢索也不 rerank
        Given 一個 mode 為 "fast" 且 rerank 開啟、沒有 worker 的 bot，檢索分數 0.85
        When 以 web 送出訊息
        Then 共用檢索應以 rerank_enabled false 被呼叫

    Scenario: deep bot 的 worker 開快速道時，rerank 依 bot 設定
        Given 一個 mode 為 "deep" 且 rerank 開啟、worker 開啟直接檢索的 bot，檢索分數 0.85
        When 以 web 送出訊息
        Then 共用檢索應以 rerank_enabled true 被呼叫
        And Agent 應以 max_tool_calls 1 被呼叫

    Scenario: deep bot 沒有旗標 — 完整 ReAct
        Given 一個 mode 為 "deep" 且沒有 worker 的 bot，檢索分數 0.85
        When 以 web 送出訊息
        Then 共用檢索不應被呼叫
        And Agent 應以 max_tool_calls 5 被呼叫

    Scenario: LINE 通路的 fast bot 同樣走快速道
        Given LINE 用例與 mode 為 "fast" 且沒有 worker 的 bot
        When 系統處理一則 LINE 訊息
        Then LINE Agent 應以 max_tool_calls 1 被呼叫

    Scenario: worker 建立與更新可設定 direct_retrieval
        Given worker 用例
        When 建立 worker 時 direct_retrieval 為 true，再更新為 false
        Then 儲存的 worker direct_retrieval 應依序為 true 與 false

    Scenario Outline: bot mode 值域驗證
        Given 一個既有的 bot
        When 將 bot mode 更新為 "<mode>"
        Then 結果應為 <outcome>

        Examples:
            | mode  | outcome |
            | fast  | saved   |
            | deep  | saved   |
            | turbo | error   |

    Scenario: bot mode 進入設定快照
        Given 一個 mode 為 "deep" 的 bot 實體
        When 取快照後把 mode 改為 "fast" 再取一次快照
        Then 快照應含 "mode" 且 diff 應列出 "mode"
