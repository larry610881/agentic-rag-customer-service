Feature: Bulk Ingest — External Producer Batch Upload
    為了讓外部 producer（例如 PMO 平台）可以一次推 100 筆紀錄到 RAG，
    POST /knowledge-bases/{kb_id}/documents/bulk 接受 list of items
    （含 content + filename + metadata），每筆走既有 process_document
    pipeline；若 metadata 帶 (source, source_id) 則自動 dedup（先刪舊再 insert）。
    （5e80c3f Outbox Phase C 起，dedup 的 vector 刪除改寫 vector.delete outbox
    事件，由 worker 的 drain_outbox 排程非同步套用。）

    Scenario: 一次成功上傳 3 筆 documents
        Given 已登入為租戶 "Alpha Corp" 並建立知識庫 "AuditLogs"
        When 我送出 POST /bulk 含 3 筆 audit_log 條目
        Then 回應狀態碼為 200
        And 回應 indexed 為 3 且 failed 為 0
        And 回應 results 應包含 3 筆 status=accepted

    Scenario: 部分失敗 — empty content 應 partial response
        Given 已登入為租戶 "Alpha Corp" 並建立知識庫 "AuditLogs"
        When 我送出 POST /bulk 含 2 筆有效 + 1 筆 empty content
        Then 回應狀態碼為 200
        And 回應 indexed 為 2 且 failed 為 1
        And 失敗那筆的 error 應包含 "content_empty"

    Scenario: 帶 source / source_id 重複推送 — 自動 dedup
        Given 已登入為租戶 "Alpha Corp" 並建立知識庫 "AuditLogs"
        When 我送出 POST /bulk 含 1 筆 source "audit_log" / source_id "12345"
        And outbox drain 排程執行一次
        And 再次送出同樣的 POST /bulk 含 1 筆 source "audit_log" / source_id "12345"
        And outbox drain 排程執行一次
        Then 第二次呼叫前應觸發 vector_store.delete 帶 source / source_id filter
        And 兩次回應 indexed 都為 1

    Scenario: 超過 100 筆應回 422
        Given 已登入為租戶 "Alpha Corp" 並建立知識庫 "AuditLogs"
        When 我送出 POST /bulk 含 101 筆 documents
        Then 回應狀態碼為 422
