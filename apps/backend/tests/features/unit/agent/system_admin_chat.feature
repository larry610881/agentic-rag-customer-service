Feature: System Admin 跨租戶 Chat
  系統管理員可以使用任何租戶的 Bot 進行對話測試

  Scenario: System Admin 使用其他租戶的 Bot 發訊息成功
    Given 系統管理員（tenant "00000000-0000-0000-0000-000000000000"）
    And 一個屬於租戶 "tenant-001" 的 bot "bot-abc"
    When 系統管理員透過該 Bot 發送訊息
    Then 訊息應使用 bot 所屬租戶的 tenant_id 發送
    And 不應拋出 DomainException

  Scenario: 一般租戶使用不屬於自己的 Bot 仍應失敗
    Given 租戶 "tenant-001" 嘗試使用屬於 "tenant-002" 的 bot "bot-xyz"
    When 透過 Use Case 發送訊息
    Then 應拋出 DomainException 且訊息包含 "does not belong to tenant"
