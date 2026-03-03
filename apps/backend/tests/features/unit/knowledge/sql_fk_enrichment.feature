Feature: SQL FK Enrichment
  根據外鍵關聯自動豐富化每行資料

  Scenario: 單一 FK 豐富化附加關聯表描述欄位
    Given 一組含 orders 和 customers 表的 schema 與資料且 orders 有 FK 指向 customers
    When 執行 FK 豐富化
    Then orders 的每行應附加對應 customer 的描述欄位

  Scenario: FK 目標列不存在時不附加
    Given 一組含 FK 但目標表資料中無對應 PK 值
    When 執行 FK 豐富化
    Then 該行不應附加任何關聯資料

  Scenario: 多重 FK 同時豐富化
    Given 一組含 order_items 表且有 FK 分別指向 orders 和 products
    When 執行 FK 豐富化
    Then order_items 的每行應同時附加 orders 和 products 的描述欄位

  Scenario: 豐富化時排除噪音欄位
    Given 一組含 FK 且目標表有 _id 和 _at 結尾的欄位
    When 執行 FK 豐富化
    Then 附加的描述欄位應排除 _id 和 _at 結尾的噪音欄位
