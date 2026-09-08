Feature: 知識庫問答模式 — bot mode kb (Knowledge-Only Mode)
    身為只需要知識庫查詢的租戶
    我想要 bot 設成「知識庫問答」模式後，每題只做檢索與一次生成
    以便不用工具、不升級 ReAct、未命中時回固定話術，三通路行為一致

    Scenario: kb bot 檢索命中 — 單次生成且無任何工具
        Given 一個 mode 為 "kb" 且沒有 worker 的 bot，檢索分數 0.85
        When 以 web 送出訊息
        Then Agent 應以空工具集被呼叫
        And 共用檢索應被呼叫 1 次
        And 意圖分類器不應以分流方式被呼叫（Issue #75：僅不帶 worker 的攻擊判定）

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

    # Issue #84：Google 曾因 thought_signature 被 langchain-openai 剝除而無法綁工具，
    # 改用原生 SDK 後已解除封鎖；封鎖機制保留，供未來其他不支援的供應商使用。
    Scenario Outline: 各供應商都可儲存帶工具的 bot 設定
        Given 一個租戶可用全部內建工具的環境
        When 以供應商 "<provider>" 與工具 "<tools>" 儲存 bot 設定
        Then 儲存結果應為 <outcome>

        Examples:
            | provider  | tools                            | outcome |
            | google    | rag_query                        | saved   |
            | google    | rag_query,transfer_to_human_agent| saved   |
            | google    | -                                | saved   |
            | openai    | rag_query                        | saved   |
            | ollama    | rag_query,query_dm_with_image    | saved   |
            | anthropic | rag_query                        | saved   |

    Scenario: 供應商被列為不支援工具時，帶工具的設定仍會被擋下
        Given 一個租戶可用全部內建工具的環境
        And 供應商 "legacy-provider" 被列為不支援工具
        When 以供應商 "legacy-provider" 與工具 "rag_query" 儲存 bot 設定
        Then 儲存結果應為 error

    Scenario: 綁工具的 Google 走原生 ChatModel，未綁工具時維持相容端點
        Given 一個 Google 供應商的 ReAct 服務
        When 以 <with_tools> 解析聊天模型
        Then 使用的 ChatModel 類型應為 "<kind>"

        Examples:
            | with_tools | kind                    |
            | 有工具     | ChatGoogleGenerativeAI  |
            | 沒有工具   | ChatOpenAI              |
