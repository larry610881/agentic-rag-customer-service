Feature: 快速道共用管線 (Shared Direct Retrieval)
    身為平台
    我想要 workflow 快速道（direct_retrieval）由 web / widget / LINE 共用同一份實作
    以便快速道 bot 在任一通路都只付「分類 + 單次生成」兩次 LLM

    Scenario Outline: web / widget 命中快速道 worker — 檢索過門檻後單次生成
        Given 一個開啟直接檢索的 Worker 且共用檢索結果分數為 0.85
        When 以來源 "<source>" 以非串流方式送出訊息
        Then Agent 應以 max_tool_calls 1 且無檢索工具被呼叫
        And 生成 Prompt 應包含 "板橋店 2 樓"
        And 回應來源應含 1 筆且 chunk_id 為 "c-1"

        Examples:
            | source |
            | web    |
            | widget |

    Scenario: web 串流命中快速道 — 補發 sources 事件
        Given 一個開啟直接檢索的 Worker 且共用檢索結果分數為 0.85
        When 以串流方式送出訊息並收集事件
        Then Agent 串流應以 max_tool_calls 1 被呼叫
        And 事件中應含 1 個 sources 事件且 chunk_id 為 "c-1"

    Scenario: web 檢索未過門檻 — 升級完整 ReAct
        Given 一個開啟直接檢索的 Worker 且共用檢索結果分數為 0.10
        When 以來源 "web" 以非串流方式送出訊息
        Then Agent 應以完整工具模式被呼叫

    Scenario: web 未開啟直接檢索 — 行為不變
        Given 一個未開啟直接檢索的 Worker
        When 以來源 "web" 以非串流方式送出訊息
        Then 共用檢索不應被呼叫
        And Agent 應以完整工具模式被呼叫

    Scenario: fast profile 的 bot 快速道鎖定 rerank 關閉（Issue #66：deep bot 依設定）
        Given 一個 mode 為 fast 且 bot 開啟 rerank 的 Worker
        When 以來源 "web" 以非串流方式送出訊息
        Then 共用檢索應以 rerank_enabled false 被呼叫

    Scenario: LINE 快速道改用共用服務後行為一致
        Given LINE 用例以共用檢索服務建構且 Worker 開啟直接檢索
        When 系統處理一則命中該 Worker 的 LINE 訊息
        Then LINE Agent 應以 max_tool_calls 1 被呼叫
        And 共用檢索應被呼叫 1 次

    # ── Gemini 對應 ──

    Scenario Outline: Gemini 模型接受 reasoning_effort 對應 thinking level
        When 以模型 "<model>" 檢查 reasoning_effort "<effort>"
        Then 允許結果應為 <allowed> 且正規化值為 "<normalized>"

        Examples:
            | model             | effort  | allowed | normalized |
            | gemini-3.7-flash  | low     | true    | low        |
            | gemini-3.7-flash  | minimal | true    | low        |
            | gemini-3.7-flash  | none    | true    | none       |
            | gemini-3.7-flash  | high    | true    | high       |
            | gpt-5.4           | low     | false   | low        |
            | gpt-5.4           | none    | true    | none       |
            | gpt-4o            | low     | false   | low        |
