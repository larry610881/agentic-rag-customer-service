Feature: System Admin 跨租戶查詢機器人
  確保 system_admin 查詢不存在的 bot 回傳 404

  Scenario: 查詢不存在的 Bot 回傳 404
    Given system_admin 已登入
    When 以 bot_id "nonexistent-bot" 發起對話
    Then 應拋出 EntityNotFoundError

  Scenario: 查詢存在的 Bot 正常取得
    Given system_admin 已登入
    And 機器人 "bot-001" 屬於租戶 "t-001"
    When 以 bot_id "bot-001" 發起對話
    Then effective_tenant_id 應為 "t-001"
