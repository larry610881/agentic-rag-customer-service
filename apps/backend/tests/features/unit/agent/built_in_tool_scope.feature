Feature: Built-in Tool Tenant Scope 過濾
  作為系統管理員
  我需要控制 built-in tool 可開放給哪些租戶
  避免一般租戶誤啟用未授權工具

  Scenario: Global scope 工具所有租戶都可見
    Given 一個 "global" scope 的工具 "rag_query"
    When 租戶 "tenant-a" 查詢可用工具
    Then 結果應包含 "rag_query"

  Scenario: Tenant scope 工具非白名單租戶看不到
    Given 一個 "tenant" scope 的工具 "query_dm_with_image" 白名單為 "tenant-carrefour"
    When 租戶 "tenant-other" 查詢可用工具
    Then 結果不應包含 "query_dm_with_image"

  Scenario: Tenant scope 工具白名單租戶可見
    Given 一個 "tenant" scope 的工具 "query_dm_with_image" 白名單為 "tenant-carrefour"
    When 租戶 "tenant-carrefour" 查詢可用工具
    Then 結果應包含 "query_dm_with_image"

  Scenario: 系統管理員查詢時看到所有工具含 scope 資訊
    Given 系統內已註冊 3 個 built-in tool
    When 系統管理員查詢工具清單
    Then 結果應包含 3 個工具且每個都帶 scope 欄位

  Scenario: Seed 預設資料冪等保留使用者 scope 設定
    Given DB 已有工具 "rag_query" scope 為 "tenant" 且白名單為 "tenant-a"
    When 應用啟動執行 seed_defaults
    Then "rag_query" 的 scope 仍為 "tenant"
    And "rag_query" 的白名單仍為 "tenant-a"
    And "rag_query" 的 label 更新為最新預設值
