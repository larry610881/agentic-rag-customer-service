Feature: 刪除知識庫文件（透過 Outbox Pattern）
  作為管理員，我要能刪除文件並確保父 + 所有 children 一起清乾淨
  Phase C 改寫：vector store 的 DELETE 改走 outbox 事件，drain worker 接手
  doc_watermark_ts = parent doc.created_at → drain 端做 id-reuse guard

  Background:
    Given 知識庫 "kb-001" 存在
    And 文件 "doc-001" 已上傳且狀態為 "processed"

  Scenario: 成功刪除文件 → 發布 outbox vector.delete 事件
    When 刪除文件 "doc-001"
    Then 文件應從資料庫移除
    And 應發布 1 筆 vector.delete outbox 事件
    And 該事件的 collection 應為 "kb_kb-001"
    And 該事件的 filters.document_id 應只含 "doc-001"
    And 該事件應帶 doc_watermark_ts 等於 parent doc.created_at
    And 不應直接呼叫 vector store

  Scenario: 刪除不存在的文件回傳錯誤
    When 刪除文件 "nonexistent"
    Then 應拋出 EntityNotFoundError
    And 不應發布任何 outbox 事件

  Scenario: 刪除 PDF 父文件 cascade — outbox event 帶父+children doc_id list
    Given 文件 "doc-001" 有 3 個 child 子頁文件
    When 刪除文件 "doc-001"
    Then 文件應從資料庫移除
    And 應發布 1 筆 vector.delete outbox 事件
    And 該事件的 filters.document_id 應同時帶父與所有 children 的 document_id
    And 所有 children 也應從資料庫移除
