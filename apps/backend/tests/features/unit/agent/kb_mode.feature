Feature: 知識庫問答模式 — bot mode kb (Knowledge-Only Mode)
    身為只需要知識庫查詢的租戶
    我想要 bot 設成「知識庫問答」模式後，每題只做檢索與一次生成
    以便不用工具、不升級 ReAct、未命中時回固定話術，三通路行為一致

    Scenario: kb bot 檢索命中 — 單次生成且無任何工具
        Given 一個 mode 為 "kb" 且沒有 worker 的 bot，檢索分數 0.85
        When 以 web 送出訊息
        Then Agent 應以空工具集被呼叫
        And 共用檢索應被呼叫 1 次
        And 意圖分類器不應被呼叫

    Scenario: kb bot 檢索未命中 — 回未命中話術且不呼叫生成模型
        Given 一個 mode 為 "kb" 且未命中話術為 "這個問題不在我的服務範圍內" 的 bot，檢索分數 0.10
        When 以 web 送出訊息
        Then 回覆內容應為 "這個問題不在我的服務範圍內"
        And Agent 不應被呼叫
        And trace 應含 "kb_miss" 節點

    Scenario: kb bot 未設定未命中話術時使用系統預設文案
        Given 一個 mode 為 "kb" 且未命中話術為 "-" 的 bot，檢索分數 0.10
        When 以 web 送出訊息
        Then 回覆內容應為系統預設未命中話術
        And Agent 不應被呼叫

    Scenario: kb bot 即使開了 rerank 與記憶也不生效
        Given 一個 mode 為 "kb" 且 rerank 開啟、記憶開啟、沒有 worker 的 bot，檢索分數 0.85
        When 以 web 送出訊息
        Then 共用檢索應以 rerank_enabled false 被呼叫
        And 記憶抽取不應被排程

    Scenario: kb bot 串流路徑同樣走單次生成
        Given 一個 mode 為 "kb" 且沒有 worker 的 bot，檢索分數 0.85
        When 以 web 串流送出訊息
        Then 串流 Agent 應以空工具集被呼叫

    Scenario: kb bot 串流路徑未命中 — 串流回未命中話術
        Given 一個 mode 為 "kb" 且未命中話術為 "這個問題不在我的服務範圍內" 的 bot，檢索分數 0.10
        When 以 web 串流送出訊息
        Then 串流內容應為 "這個問題不在我的服務範圍內"
        And 串流 Agent 不應被呼叫

    Scenario: LINE 通路的 kb bot 命中 — 單次生成
        Given LINE 用例與 mode 為 "kb" 且沒有 worker 的 bot，檢索分數 0.85
        When 系統處理一則 LINE 訊息
        Then LINE Agent 應以空工具集被呼叫

    Scenario: LINE 通路的 kb bot 未命中 — 回未命中話術
        Given LINE 用例與 mode 為 "kb" 且未命中話術為 "這個問題不在我的服務範圍內" 的 bot，檢索分數 0.10
        When 系統處理一則 LINE 訊息
        Then LINE 回覆文字應為 "這個問題不在我的服務範圍內"
        And LINE Agent 不應被呼叫

    Scenario Outline: bot mode 值域含 kb
        Given 一個既有的 bot
        When 將 bot mode 更新為 "<mode>"
        Then 結果應為 <outcome>

        Examples:
            | mode | outcome |
            | kb   | saved   |
            | fast | saved   |
            | deep | saved   |
            | km   | error   |

    Scenario: 未命中話術與輸出格式進入設定快照
        Given 一個 mode 為 "kb" 的 bot 實體
        When 取快照後把未命中話術改為 "換個方式問我" 再取一次快照
        Then 快照應含 "miss_reply" 且 diff 應列出 "miss_reply"
