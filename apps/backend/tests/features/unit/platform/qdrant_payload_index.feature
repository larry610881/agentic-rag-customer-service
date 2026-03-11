Feature: Qdrant Payload Index
  ensure_collection 建立 collection 後自動建立 tenant_id 和 document_id 的 payload index

  Scenario: ensure_collection 建立 payload index
    Given 一個 Qdrant Vector Store
    When 執行 ensure_collection
    Then 應建立 tenant_id 和 document_id 的 payload index
