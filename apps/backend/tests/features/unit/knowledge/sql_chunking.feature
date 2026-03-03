Feature: SQL Chunking
  SQL dump 端對端切割，每個 chunk 按表分組並保留表頭上下文

  Scenario: 完整 SQL dump 按表切割為 chunk
    Given 一段包含兩張表的完整 MySQL dump 且 chunk_size 為 500
    When 執行 SQL 分塊處理
    Then 應產生按表分組的 chunk
    And 每個 chunk 的第一行包含表頭資訊

  Scenario: chunk metadata 包含表名與行範圍
    Given 一段包含兩張表的完整 MySQL dump 且 chunk_size 為 500
    When 執行 SQL 分塊處理
    Then 每個 chunk 的 metadata 應包含 table_name 和 row_start 和 row_end

  Scenario: 空表不產生 chunk
    Given 一段包含 CREATE TABLE 但無 INSERT 資料的 SQL dump
    When 執行 SQL 分塊處理
    Then 應產生 0 個 chunk

  Scenario: content_type 為 application/sql 時路由到 SQL 策略
    Given 一個 ContentAwareTextSplitterService 已註冊 SQL 策略
    When 以 content_type "application/sql" 執行分塊
    Then SQL 策略被呼叫
