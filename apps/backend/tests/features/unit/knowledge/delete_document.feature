Feature: 刪除知識庫文件
  Background:
    Given 知識庫 "kb-001" 存在
    And 文件 "doc-001" 已上傳且狀態為 "processed"

  Scenario: 成功刪除文件及其向量資料
    When 刪除文件 "doc-001"
    Then 文件應從資料庫移除
    And 對應的向量資料應從 Milvus 移除
    And 對應的文字分塊應從資料庫移除

  Scenario: 刪除不存在的文件回傳錯誤
    When 刪除文件 "nonexistent"
    Then 應拋出 EntityNotFoundError

  Scenario: 刪除 PDF 父文件應 cascade 一併刪 children + 清 Milvus
    Given 文件 "doc-001" 有 3 個 child 子頁文件
    When 刪除文件 "doc-001"
    Then 文件應從資料庫移除
    And Milvus delete filter 應同時帶父與所有 children 的 document_id list
    And 所有 children 也應從資料庫移除
