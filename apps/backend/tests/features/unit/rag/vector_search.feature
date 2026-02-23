Feature: Vector Search
  向量搜尋服務能根據查詢向量搜尋相似結果並過濾 tenant

  Scenario: 成功搜尋向量並回傳 SearchResult 列表
    Given 向量資料庫中有 3 筆向量資料
    When 執行向量搜尋查詢
    Then 應回傳 3 筆 SearchResult

  Scenario: 搜尋結果正確過濾 tenant_id
    Given 向量資料庫中有屬於 tenant "tenant-001" 的資料
    When 以 tenant "tenant-001" 過濾條件執行搜尋
    Then 搜尋時應傳入 tenant_id "tenant-001" 過濾條件

  Scenario: 搜尋結果低於閾值回傳空列表
    Given 向量資料庫中的資料分數均低於閾值
    When 執行向量搜尋查詢
    Then 應回傳空的搜尋結果列表
