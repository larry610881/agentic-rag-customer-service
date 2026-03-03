Feature: SQL Schema Parsing
  SQL dump 檔案的方言偵測與 DDL 解析

  Scenario: 偵測 MySQL 方言
    Given 一段包含 backtick 和 ENGINE= 的 SQL dump
    When 執行方言偵測
    Then 結果應為 mysql

  Scenario: 偵測 PostgreSQL 方言
    Given 一段包含 COPY FROM stdin 和 serial 的 SQL dump
    When 執行方言偵測
    Then 結果應為 postgresql

  Scenario: 解析 MySQL CREATE TABLE 取得欄位
    Given 一段 MySQL CREATE TABLE 語句
    When 執行 DDL 解析
    Then 應解析出正確的表名與欄位清單

  Scenario: 解析 PostgreSQL CREATE TABLE 取得欄位
    Given 一段 PostgreSQL CREATE TABLE 語句
    When 執行 DDL 解析
    Then 應解析出正確的表名與欄位清單

  Scenario: 解析 FK 約束建立關聯圖
    Given 一段包含 FOREIGN KEY 約束的 CREATE TABLE 語句
    When 執行 DDL 解析
    Then 應解析出正確的外鍵關聯
