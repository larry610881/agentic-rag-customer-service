Feature: Source Tracking — DELETE by-source 端點
    為了讓外部 producer（例如 PMO 平台）在 source record 被刪除時連動清理 RAG 索引，
    租戶可透過 DELETE /by-source 端點，依照 (source, source_ids) 一次刪掉
    Milvus 中對應 chunks。

    Scenario: DELETE /by-source 單一 source_id — 204 + Milvus delete 帶正確 filter
        Given 已登入為租戶 "Alpha Corp" 並建立知識庫 "AuditLogs"
        When 我送出 DELETE /by-source 帶 source "audit_log" 與 source_ids ["12345"]
        Then 回應狀態碼為 204
        And vector_store.delete 應被呼叫且 filter 為 source "audit_log" 與 source_ids ["12345"]

    Scenario: DELETE /by-source 多個 source_ids — filter 用 list 形式（IN operator）
        Given 已登入為租戶 "Alpha Corp" 並建立知識庫 "AuditLogs"
        When 我送出 DELETE /by-source 帶 source "audit_log" 與 source_ids ["12345","12346","12347"]
        Then 回應狀態碼為 204
        And vector_store.delete 的 filter source_ids 應為 list 且長度為 3

    Scenario: DELETE /by-source 跨租戶應回 404（tenant isolation）
        Given 已登入為租戶 "Alpha Corp" 並建立知識庫 "AuditLogs"
        And 切換為另一個租戶 "Beta Corp" 重新登入
        When 我送出 DELETE /by-source 對 Alpha 的 KB 帶 source "audit_log" 與 source_ids ["x"]
        Then 回應狀態碼為 404

    Scenario: DELETE /by-source 對不存在的 KB 回 404
        Given 已登入為租戶 "Alpha Corp"
        When 我送出 DELETE /by-source 對不存在的 KB 帶 source "audit_log" 與 source_ids ["x"]
        Then 回應狀態碼為 404

    Scenario: DELETE /by-source 不允許空 source_ids
        Given 已登入為租戶 "Alpha Corp" 並建立知識庫 "AuditLogs"
        When 我送出 DELETE /by-source 帶 source "audit_log" 與空 source_ids 列表
        Then 回應狀態碼為 422
