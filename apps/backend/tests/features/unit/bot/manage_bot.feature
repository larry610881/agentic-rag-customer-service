Feature: 管理機器人
  作為系統管理員，我要能更新、刪除和查詢機器人

  Background:
    Given 租戶 "t-001" 有一個機器人 "客服 Bot"

  Scenario: 更新機器人 LLM 參數
    When 更新機器人的 temperature 為 0.7
    Then 機器人的 temperature 應為 0.7

  Scenario: 更新機器人名稱
    When 更新機器人名稱為 "新客服 Bot"
    Then 機器人名稱應為 "新客服 Bot"

  Scenario: 刪除機器人
    When 刪除機器人
    Then 機器人應從資料庫移除

  Scenario: 刪除不存在的機器人
    When 刪除機器人 "nonexistent"
    Then 應拋出 EntityNotFoundError

  Scenario: 取得機器人詳情
    When 取得機器人詳情
    Then 應回傳機器人資訊
    And 機器人名稱應為 "客服 Bot"

  Scenario: 列出租戶所有機器人
    When 列出租戶 "t-001" 的機器人
    Then 應回傳 1 個機器人
