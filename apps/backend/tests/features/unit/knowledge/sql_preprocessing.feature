Feature: SQL Preprocessing
  SQL dump 前處理：移除註解、SET 語句、LOCK TABLES 等非資料內容

  Scenario: 移除 SQL 單行註解
    Given 一段包含 -- 單行註解的 SQL 文字
    When 執行 SQL 清洗
    Then 結果不應包含 -- 開頭的註解行

  Scenario: 移除 SQL 多行註解
    Given 一段包含 /* */ 多行註解的 SQL 文字
    When 執行 SQL 清洗
    Then 結果不應包含多行註解

  Scenario: 移除 SET 語句
    Given 一段包含 SET 語句的 SQL 文字
    When 執行 SQL 清洗
    Then 結果不應包含 SET 語句

  Scenario: 移除 LOCK TABLES 和 UNLOCK TABLES 語句
    Given 一段包含 LOCK TABLES 和 UNLOCK TABLES 的 SQL 文字
    When 執行 SQL 清洗
    Then 結果不應包含 LOCK TABLES 和 UNLOCK TABLES 語句

  Scenario: TextPreprocessor 處理 application/sql 時呼叫 SQL 清洗
    Given 一段包含 -- 註解的 SQL 文字
    When 以 application/sql content_type 執行文字前處理
    Then 結果不應包含 -- 開頭的註解行
