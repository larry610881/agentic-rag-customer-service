Feature: 查詢供應商設定 (Get Provider Setting)
  身為系統管理員
  我想要查詢單一供應商設定

  Scenario: 成功查詢存在的供應商設定
    Given 系統中有 ID 為 "ps-001" 的供應商設定
    When 我查詢供應商設定 "ps-001"
    Then 應回傳該供應商設定

  Scenario: 查詢不存在的供應商設定應失敗
    Given 系統中沒有 ID 為 "ps-999" 的供應商設定
    When 我查詢供應商設定 "ps-999"
    Then 應拋出供應商設定不存在的錯誤
