Feature: Tool Registry 工具註冊中心
  作為系統，我需要集中管理工具的後設資料和實例

  Scenario: 註冊並取得工具描述
    Given 一個空的 ToolRegistry
    When 註冊工具 "rag_query" 描述為 "查詢知識庫"
    And 註冊工具 "query_products" 描述為 "查詢商品"
    Then get_descriptions 應回傳 2 個工具描述
    And "rag_query" 的描述應為 "查詢知識庫"

  Scenario: 篩選特定工具描述
    Given 一個包含 "rag_query" 和 "query_products" 的 ToolRegistry
    When 以 ["rag_query"] 篩選 get_descriptions
    Then 應只回傳 1 個工具描述

  Scenario: 註冊並取得 LangChain 工具實例
    Given 一個空的 ToolRegistry
    When 註冊工具 "rag_query" 並附帶 LangChain 工具實例
    Then get_tools 應回傳 1 個工具實例

  Scenario: 未註冊的工具不影響查詢
    Given 一個包含 "rag_query" 的 ToolRegistry
    When 以 ["not_exist"] 篩選 get_tools
    Then 應回傳空的工具列表
