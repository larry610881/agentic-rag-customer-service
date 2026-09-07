Feature: 用量記帳覆蓋 (Usage Accounting Coverage)
    身為平台
    我想要每一條花費 token 的路徑都寫入 token_usage_records，且 token 數來自供應商回傳
    以便點數制上線後不會少扣、輔助 LLM 成本能歸屬到正確的 bot

    # ── Embedding 服務回傳用量（Issue #73 根因）──

    Scenario: OpenAI embedding 服務回傳供應商用量
        Given OpenAI embedding API 回傳 2 個向量且 usage total_tokens 為 37
        When 對 2 筆文字呼叫 embed_texts_with_usage
        Then EmbeddingResult 的 total_tokens 應為 37 且 model 應為服務模型
        And EmbeddingResult 應含 2 個向量

    Scenario: 快取包裝層命中時回傳 cache_hit 且 total_tokens 為 0
        Given 快取包裝層的快取內已有查詢 "怎麼退貨" 的向量
        When 對 "怎麼退貨" 呼叫 embed_query_with_usage
        Then 結果 cache_hit 應為 true 且 total_tokens 應為 0
        And 內層 embedding 服務不應被呼叫

    Scenario: 快取包裝層未命中時透傳內層用量
        Given 快取包裝層的快取為空且內層服務回傳 total_tokens 12
        When 對 "怎麼退貨" 呼叫 embed_query_with_usage
        Then 結果 cache_hit 應為 false 且 total_tokens 應為 12

    Scenario: 動態代理透傳內層用量
        Given 動態代理的內層服務回傳 total_tokens 9
        When 透過動態代理呼叫 embed_texts_with_usage
        Then 結果 total_tokens 應為 9

    Scenario: 共用記帳 helper 在快取命中時不入帳
        Given 已注入可用的 record_usage
        When 以 cache_hit 的 EmbeddingResult 呼叫 account_embedding
        Then record_usage 不應被呼叫

    Scenario: 共用記帳 helper 在 record_usage 失敗時不拋例外
        Given 注入的 record_usage 執行時會拋出例外
        When 以 total_tokens 20 的 EmbeddingResult 呼叫 account_embedding
        Then account_embedding 不應拋出例外

    # ── 文件管線：處理與重處理三處對齊 ──

    Scenario Outline: 文件管線花了 token 就必有一筆 usage
        Given 文件管線 "<pipeline>" 已注入 record_usage
        And 文件解析消耗 OCR input 500 output 80
        And 上下文服務消耗 input 300 output 40
        And embedding 服務回傳 total_tokens 25
        When 執行文件管線
        Then 應記錄 request_type "ocr" 的用量 input 500 output 80
        And 應記錄 request_type "contextual_retrieval" 的用量 input 300 output 40
        And 應記錄 request_type "embedding" 的用量 input 25 且 kb_id 為文件的 kb

        Examples:
            | pipeline  |
            | process   |
            | reprocess |

    # ── 查詢 embedding：單點記帳、所有通路共用 ──

    Scenario Outline: 每輪檢索的查詢 embedding 都入帳並帶 bot_id
        Given 檢索用例已注入 record_usage 且 embedding 服務每次回傳 7 tokens
        When 以進入路徑 "<entry>" 執行檢索
        Then 應記錄 request_type "query_embedding" 的用量 input 7
        And 所有 "query_embedding" 紀錄的 bot_id 應為 "<bot_id>"

        Examples:
            | entry              | bot_id    |
            | command_bot_id     | bot-fast  |
            | trace_context      | bot-tool  |
            | playground         | bot-pg    |
            | unified_search     | none      |

    Scenario: 查詢 embedding 快取命中不入帳
        Given 檢索用例已注入 record_usage 且 embedding 服務回傳 cache_hit
        When 以進入路徑 "command_bot_id" 執行檢索
        Then 不應有 request_type "query_embedding" 的紀錄

    # ── 其他未入帳 / 估算的 embedding 呼叫 ──

    Scenario: 單 chunk 重新向量化使用供應商回傳的 token 數
        Given reembed 用例的 embedding 服務回傳 total_tokens 33
        When 執行單 chunk 重新向量化
        Then 應記錄 request_type "embedding" 的用量 input 33

    Scenario: 對話摘要語意搜尋入帳到系統租戶
        Given 對話搜尋用例的 embedding 服務回傳 total_tokens 11
        When 執行對話摘要語意搜尋
        Then 應記錄 request_type "embedding" 的用量 input 11
        And 該筆紀錄的 tenant 應為系統租戶

    Scenario: 對話摘要服務回傳實際 embedding 用量
        Given 摘要服務的 LLM 回傳摘要且 embedding 服務回傳 total_tokens 14
        When 執行對話摘要
        Then 摘要結果的 embedding_tokens 應為 14

    Scenario: DM 中繼資料抽取以 dm_metadata 類別記帳
        Given DM 中繼資料抽取器消耗 input 1000 output 200
        When 執行 DM 中繼資料抽取
        Then 應記錄 request_type "dm_metadata" 的用量 input 1000 output 200

    # ── 輔助 LLM 呼叫 bot_id 歸屬 ──

    Scenario Outline: 輔助 LLM 呼叫紀錄帶 bot_id
        Given 輔助 LLM 路徑 "<path>" 已注入 record_usage
        When 以 bot "bot-aux" 執行輔助 LLM 路徑
        Then 該筆用量紀錄的 bot_id 應為 "bot-aux"

        Examples:
            | path              |
            | rerank            |
            | query_rewrite     |
            | hyde              |
            | history_summary   |
            | memory_extraction |

    # ── UsageCategory 死值清理與 enum 守門 ──

    Scenario Outline: 已淘汰的類別拒絕新寫入
        Given 一個 RecordUsageUseCase
        When 以 request_type "<category>" 寫入用量
        Then 應拋出 ValueError 且 usage repository 不應被呼叫

        Examples:
            | category |
            | rag      |
            | guard    |

    Scenario: 程式碼中 request_type 一律使用 UsageCategory enum
        When 掃描 src 目錄中的 request_type 字串字面值
        Then 不應有任何檔案使用 request_type 字串字面值

    Scenario: 每個未淘汰的 UsageCategory 都有生產者
        When 掃描 src 目錄中每個 UsageCategory 成員的引用
        Then 每個未淘汰的類別都應在 src 中被引用
