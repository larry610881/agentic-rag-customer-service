Feature: 對話紀錄依 bot_id 隔離
  作為系統
  我需要在對話中記錄 bot_id
  以便同一租戶下不同 Bot 的對話可以分開查詢

  Scenario: 建立對話時儲存 bot_id
    Given 一個屬於 tenant "tenant-001" 且 bot 為 "bot-abc" 的新對話
    When 透過 Use Case 儲存該對話
    Then Repository 應收到 bot_id 為 "bot-abc" 的對話

  Scenario: 無 bot_id 的對話 bot_id 為空
    Given 一個屬於 tenant "tenant-001" 且未指定 bot 的新對話
    When 透過 Use Case 儲存該對話
    Then Repository 應收到 bot_id 為空的對話

  Scenario: 依 bot_id 過濾對話列表
    Given 租戶 "tenant-001" 有 3 筆對話，其中 2 筆屬於 bot "bot-abc"
    When 以 bot_id "bot-abc" 查詢對話列表
    Then 應回傳 2 筆對話

  Scenario: 無 bot_id 過濾時回傳全部對話
    Given 租戶 "tenant-001" 有 3 筆對話，其中 2 筆屬於 bot "bot-abc"
    When 不帶 bot_id 查詢對話列表
    Then 應回傳 3 筆對話

  Scenario: 使用不屬於該租戶的 bot 發送訊息應失敗
    Given 租戶 "tenant-001" 嘗試使用屬於 "tenant-002" 的 bot "bot-xyz"
    When 透過 Use Case 發送訊息
    Then 應拋出 DomainException 且訊息包含 "does not belong to tenant"
