Feature: Product Search
  商品搜尋工具能根據關鍵字搜尋商品

  Scenario: 搜尋關鍵字回傳相關商品列表
    Given 資料庫中有商品資料
    When 搜尋關鍵字 "electronics"
    Then 應回傳成功的商品搜尋結果
    And 結果應包含商品列表

  Scenario: 搜尋無結果回傳空列表
    Given 資料庫中無匹配商品
    When 搜尋關鍵字 "nonexistent_xyz"
    Then 應回傳成功的商品搜尋結果
    And 商品列表應為空
