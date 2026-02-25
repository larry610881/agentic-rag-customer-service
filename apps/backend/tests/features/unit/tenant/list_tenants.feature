Feature: 列出租戶 (List Tenants)
  身為系統管理員
  我想要列出所有租戶

  Scenario: 列出所有租戶
    Given 系統中有 2 個租戶
    When 我列出所有租戶
    Then 應回傳 2 個租戶
