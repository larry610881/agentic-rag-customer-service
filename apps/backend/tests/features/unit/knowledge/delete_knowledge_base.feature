Feature: 刪除知識庫（透過 Outbox Pattern 確保 PG ↔ Milvus 一致性）
  作為管理員，我要能刪除知識庫並確保所有關聯資料一起清乾淨
  Phase B 改寫：用 outbox vector.drop_collection 事件取代直接呼叫 Milvus
  順序保證：PG cascade delete 與 outbox publish 在同一 transaction
  → commit 後 drain worker 才會對 Milvus drop collection

  Background:
    Given 知識庫 "kb-001" 存在且包含文件

  Scenario: 成功刪除知識庫並發布 outbox vector.drop_collection 事件
    When 刪除知識庫 "kb-001"
    Then 知識庫應從資料庫移除
    And 應發布 1 筆 vector.drop_collection outbox 事件
    And 該事件的 collection 應為 "kb_kb-001"
    And 不應直接呼叫 vector store

  Scenario: outbox publish 必須先於 PG delete 呼叫
    When 刪除知識庫 "kb-001"
    Then publish_outbox 應先於 kb_repo.delete 被呼叫

  Scenario: 刪除不存在的知識庫回傳錯誤
    When 刪除知識庫 "nonexistent"
    Then 應拋出 EntityNotFoundError
    And 不應發布任何 outbox 事件
