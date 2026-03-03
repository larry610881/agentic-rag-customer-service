Feature: SQL Data Extraction
  從 SQL dump 中提取 INSERT / COPY 資料列

  Scenario: 解析 MySQL INSERT INTO 語句提取資料
    Given 一段包含 INSERT INTO 的 MySQL dump
    When 執行資料提取
    Then 應取得正確的表名與資料列

  Scenario: 解析 PostgreSQL COPY 語句提取資料
    Given 一段包含 COPY FROM stdin 的 PostgreSQL dump
    When 執行資料提取
    Then 應取得正確的表名與資料列

  Scenario: 合併同一表的多次 INSERT
    Given 一段包含同一表兩次 INSERT INTO 的 MySQL dump
    When 執行資料提取
    Then 該表的資料列應合併為完整集合

  Scenario: INSERT 中含引號和逗號的值能正確解析
    Given 一段 INSERT INTO 的值包含引號和逗號
    When 執行資料提取
    Then 應正確解析含特殊字元的值
