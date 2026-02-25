Feature: Product Recommend
  商品推薦工具能搜尋系統知識庫進行商品推薦

  Scenario: 成功推薦商品
    Given 租戶有系統知識庫
    When 請求推薦 "推薦一個電子產品"
    Then 應回傳成功的推薦結果
    And 結果應包含推薦答案

  Scenario: 尚未建立商品目錄
    Given 租戶沒有系統知識庫
    When 請求推薦 "推薦一個電子產品"
    Then 應回傳尚未建立商品目錄的錯誤

  Scenario: 查無相關商品
    Given 租戶有系統知識庫但無相關商品
    When 請求推薦 "不存在的商品類別 XYZ"
    Then 應回傳成功的推薦結果
    And 結果應提示找不到相關商品
