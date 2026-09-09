Feature: 情境預設與可組合設定 (Mode as preset, not runtime override)
    身為租戶管理員
    我要能自由組合檢索與推理的各個開關，並用情境預設一次填好常見組合
    以便後台顯示什麼就是實際行為什麼，不會有「開關打開卻不生效」的情況

    # 設計（Issue #92）：
    #   mode 只是「上次套用的預設」標籤，**不驅動任何行為**。
    #   真正決定行為的是各自的欄位：direct_retrieval / escalate_on_miss /
    #   rerank_enabled / query_rewrite_enabled / hyde_enabled / memory_enabled / enabled_tools。
    # 反例來源：kb 模式在管線硬關 rerank，後台開關可打開、存檔成功、實際無效且無提示。

    # --- 預設只填值，不覆蓋 ---

    Scenario: 套用「知識庫問答」預設會填好各個開關
        When 套用情境預設 "kb"
        Then 設定 "direct_retrieval" 應為 true
        And 設定 "escalate_on_miss" 應為 false
        And 設定 "rerank_enabled" 應為 false
        And 設定 "query_rewrite_enabled" 應為 false
        And 設定 "hyde_enabled" 應為 false
        And 設定 "memory_enabled" 應為 false
        And 設定的可用工具應為空

    Scenario: 套用「深度道」預設會開回完整能力
        When 套用情境預設 "deep"
        Then 設定 "direct_retrieval" 應為 false
        And 設定 "escalate_on_miss" 應為 true
        And 設定 "rerank_enabled" 應為 true

    Scenario: 套用預設後仍可自行偏離，且偏離值真的生效
        Given 已套用情境預設 "kb"
        When 我把 "rerank_enabled" 改為 true
        Then 解析後的檢索計畫應允許 rerank

    Scenario: mode 欄位只是標籤，不影響行為
        Given 一個 bot 其 mode 為 "kb" 但 rerank_enabled 為 true
        When 解析該 bot 的檢索計畫
        Then 解析後的檢索計畫應允許 rerank

    # --- 未命中行為改由欄位決定 ---

    Scenario: escalate_on_miss 為 false 時未命中回固定話術
        Given 一個 bot 其 direct_retrieval 為 true 且 escalate_on_miss 為 false
        When 檢索未達門檻
        Then 應回未命中話術且不升級推理

    Scenario: escalate_on_miss 為 true 時未命中升級推理
        Given 一個 bot 其 direct_retrieval 為 true 且 escalate_on_miss 為 true
        When 檢索未達門檻
        Then 應升級推理

    # --- 後端第二層防呆（前端已在選取當下 disable，此處守 API 直接呼叫）---

    Scenario Outline: 無效組合由後端擋下
        When 我送出設定 "<field>" 為 <value> 但前置條件未滿足
        Then 應被拒絕並說明缺少的前置條件 "<prerequisite>"

        Examples:
            | field                 | value | prerequisite       |
            | rerank_enabled        | true  | knowledge_base_ids |
            | query_rewrite_enabled | true  | knowledge_base_ids |
            | hyde_enabled          | true  | knowledge_base_ids |
            | escalate_on_miss      | true  | enabled_tools      |

    Scenario: 前置條件滿足時同樣的設定可以通過
        Given 一個 bot 已綁定知識庫
        When 我送出設定 "rerank_enabled" 為 true 但前置條件已滿足
        Then 設定應被接受
