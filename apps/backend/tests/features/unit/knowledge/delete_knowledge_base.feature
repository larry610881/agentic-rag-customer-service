Feature: 刪除知識庫
  Background:
    Given 知識庫 "kb-001" 存在且包含文件

  Scenario: 成功刪除知識庫及所有關聯資料
    When 刪除知識庫 "kb-001"
    Then 知識庫應從資料庫移除
    And 所有文件的向量資料應從 Milvus 移除
    And 所有文件及分塊應從資料庫移除

  Scenario: 刪除不存在的知識庫回傳錯誤
    When 刪除知識庫 "nonexistent"
    Then 應拋出 EntityNotFoundError
