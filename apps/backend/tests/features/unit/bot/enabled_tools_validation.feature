Feature: Bot enabled_tools 權限驗證
  作為租戶管理員
  我在建立或更新 Bot 時
  系統應驗證 enabled_tools 是否為租戶可存取的 built-in tool
  防止啟用未授權工具

  Scenario: 建立 Bot 含未授權 built-in tool 應拋出驗證錯誤
    Given 租戶 "tenant-a" 可存取的 built-in tools 為 "rag_query"
    When 我以租戶 "tenant-a" 驗證 enabled_tools "rag_query,query_dm_with_image"
    Then 應拋出驗證錯誤且訊息包含 "query_dm_with_image"

  Scenario: enabled_tools 全部為 accessible 應通過
    Given 租戶 "tenant-a" 可存取的 built-in tools 為 "rag_query,transfer_to_human_agent"
    When 我以租戶 "tenant-a" 驗證 enabled_tools "rag_query"
    Then 驗證應通過

  Scenario: 非 built-in tool 名稱略過驗證
    Given 租戶 "tenant-a" 可存取的 built-in tools 為 "rag_query"
    When 我以租戶 "tenant-a" 驗證 enabled_tools "rag_query,mcp_search_catalog"
    Then 驗證應通過
