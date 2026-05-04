Feature: Unified Search — Cross-KB Multi-mode Retrieval API
    為了讓外部 producer / consumer（例如 PMO 平台）可以一次跨多個 KB
    搜尋，POST /api/v1/rag/search 接受 kb_ids list + retrieval_modes
    list + 可選 metadata filter（含 source 等 first-class 欄位），
    回傳 sources 陣列含 kb_id 標記讓前端知道哪個 KB 命中。

    Scenario: 跨多 KB unified search — 200 + 走多 KB 搜尋
        Given 已登入為租戶 "Alpha Corp" 並建立兩個知識庫 "Audit" 與 "Meetings"
        When 我送出 POST /api/v1/rag/search 含 query 與兩個 kb_ids
        Then 回應狀態碼為 200
        And 回應包含 results 陣列且每筆有 kb_id
        And vector_store.search 應對兩個 collection 都被呼叫

    Scenario: 帶 source filter — Milvus filter expression 應含 source
        Given 已登入為租戶 "Alpha Corp" 並建立兩個知識庫 "Audit" 與 "Meetings"
        When 我送出 POST /api/v1/rag/search 含 source filter "audit_log"
        Then 回應狀態碼為 200
        And vector_store.search 的 filter 應同時帶 tenant_id 與 source

    Scenario: 跨租戶呼叫 — KB 不屬本租戶應 404
        Given 已登入為租戶 "Alpha Corp" 並建立知識庫 "Audit"
        And 切換為另一個租戶 "Beta Corp" 重新登入
        When 我送出 POST /api/v1/rag/search 對 Alpha 的 KB
        Then 回應狀態碼為 404
