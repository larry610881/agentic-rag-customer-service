Feature: Vector Store Collection Index
  ensure_collection 建立 collection 後自動建立 tenant_id 和 document_id 的索引

  Scenario: ensure_collection 建立 collection 並設定索引
    Given 一個 Milvus Vector Store
    When 執行 ensure_collection
    Then 應成功建立包含 tenant_id 和 document_id 欄位的 collection
