Feature: Excel Parsing
  支援 XLSX 檔案解析

  Scenario: 解析單一 sheet XLSX
    Given 一個單一 sheet 的 XLSX 檔案
    When 解析 XLSX 檔案
    Then 應回傳包含 sheet 標記的文字

  Scenario: 多 sheet 支援
    Given 一個多 sheet 的 XLSX 檔案
    When 解析 XLSX 檔案
    Then 應回傳所有 sheet 的內容

  Scenario: 空 sheet 跳過
    Given 一個包含空 sheet 的 XLSX 檔案
    When 解析 XLSX 檔案
    Then 空 sheet 應被跳過
