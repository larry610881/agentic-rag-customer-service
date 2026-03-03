Feature: Text Preprocessing
  文件內容在分塊前進行正規化與樣板移除

  Scenario: Unicode NFC 正規化
    Given 一段包含非 NFC 字元的文字
    When 執行文字前處理
    Then 結果應為 NFC 正規化後的文字

  Scenario: 連續空白折疊
    Given 一段包含連續空白的文字
    When 執行文字前處理
    Then 連續空白應折疊為單一空格

  Scenario: 零寬字元移除
    Given 一段包含零寬字元的文字
    When 執行文字前處理
    Then 零寬字元應被移除

  Scenario: 多餘換行折疊
    Given 一段包含超過兩個連續換行的文字
    When 執行文字前處理
    Then 連續換行應折疊為兩個

  Scenario: PDF 重複頁首頁尾移除
    Given 一份多頁 PDF 文字且有重複頁首頁尾
    When 以 PDF content_type 執行文字前處理
    Then 重複出現的頁首頁尾應被移除
