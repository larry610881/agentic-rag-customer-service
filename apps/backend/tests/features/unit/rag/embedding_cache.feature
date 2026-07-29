Feature: Embedding 查詢快取 (Embedding Query Cache)
    身為系統維運者
    我想要快取查詢文字的 embedding 向量
    以便重複問句不用再打 Embedding API，降低 LINE 客服回應延遲

    Scenario: 快取未命中時呼叫內層服務並寫入快取
        Given 快取中沒有查詢 "怎麼退貨" 的向量
        When 我對 "怎麼退貨" 執行 embed_query
        Then 應呼叫內層 embedding 服務一次
        And 應將向量以 TTL 寫入快取
        And 回傳的向量應與內層服務結果一致

    Scenario: 快取命中時不呼叫內層服務
        Given 快取中已存在查詢 "怎麼退貨" 的向量
        When 我對 "怎麼退貨" 執行 embed_query
        Then 不應呼叫內層 embedding 服務
        And 回傳的向量應與快取內容一致

    Scenario: 快取讀取失敗時 fail-open 直接呼叫內層
        Given 快取服務讀取時會回傳 None
        When 我對 "怎麼退貨" 執行 embed_query
        Then 應呼叫內層 embedding 服務一次
        And 回傳的向量應與內層服務結果一致

    Scenario: 快取內容毀損時視為未命中
        Given 快取中查詢 "怎麼退貨" 的值是毀損的資料
        When 我對 "怎麼退貨" 執行 embed_query
        Then 應呼叫內層 embedding 服務一次
        And 回傳的向量應與內層服務結果一致

    Scenario: 相同文字不同模型使用不同快取鍵
        Given 兩個使用不同模型的快取 embedding 服務
        When 我分別對 "怎麼退貨" 執行 embed_query
        Then 兩者寫入快取的鍵應不相同

    Scenario: 前後空白正規化後視為同一查詢
        Given 快取中沒有查詢 "怎麼退貨" 的向量
        When 我對 "  怎麼退貨  " 執行 embed_query 後再對 "怎麼退貨" 執行
        Then 內層 embedding 服務只應被呼叫一次

    Scenario: embed_texts 批次不走快取直接委派
        Given 快取中沒有任何資料
        When 我對多筆文字執行 embed_texts
        Then 應直接委派內層服務且不讀寫快取
