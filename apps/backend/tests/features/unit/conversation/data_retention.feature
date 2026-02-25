Feature: Data Retention
  資料保留策略支援自動清理過期回饋

  Scenario: 清理超過保留期限的回饋
    Given 租戶 "t-001" 有 10 筆超過 6 個月的回饋
    When 執行資料保留清理（6 個月）
    Then 應刪除 10 筆過期回饋

  Scenario: 無過期資料時不刪除
    Given 租戶 "t-001" 無過期回饋
    When 執行資料保留清理（6 個月）
    Then 應刪除 0 筆

  Scenario: PII 遮蔽功能
    Given 一段含有 email 和手機號碼的文字
    When 執行 PII 遮蔽
    Then email 和手機應被替換為遮蔽字串
