Feature: 多知識庫 RAG 查詢
  作為使用者，我要能跨多個知識庫搜尋並合併結果

  Scenario: 跨多個知識庫搜尋並合併結果
    Given 租戶 "t-001" 有知識庫列表 "kb-001,kb-002"
    And 所有知識庫都有相關文件
    When 對知識庫 "kb-001,kb-002" 查詢 "退貨政策"
    Then 應合併兩個知識庫的搜尋結果
    And 結果應按相關度排序

  Scenario: 單一知識庫 backward compatible
    Given 租戶 "t-001" 有知識庫列表 "kb-001"
    And 所有知識庫都有相關文件
    When 對知識庫 "kb-001" 查詢 "退貨政策"
    Then 應只搜尋 "kb-001" 的結果
