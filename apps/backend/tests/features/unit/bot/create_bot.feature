Feature: 建立機器人
  作為系統管理員，我要能建立機器人並綁定知識庫

  Scenario: 成功建立綁定知識庫的機器人
    Given 租戶 "t-001" 存在
    And 知識庫 "kb-001" 和 "kb-002" 存在
    When 建立機器人名稱 "客服 Bot" 綁定知識庫 "kb-001,kb-002"
    Then 機器人應成功建立
    And 機器人應綁定 2 個知識庫
    And 機器人預設 LLM 參數應為 temperature=0.3 max_tokens=1024

  Scenario: 建立不綁定知識庫的機器人
    Given 租戶 "t-001" 存在
    When 建立機器人名稱 "簡易 Bot" 不綁定知識庫
    Then 機器人應成功建立
    And 機器人應綁定 0 個知識庫

  Scenario: 建立機器人可設定自訂 LLM 參數
    Given 租戶 "t-001" 存在
    When 建立機器人名稱 "進階 Bot" 設定 temperature=0.7 max_tokens=2048
    Then 機器人應成功建立
    And 機器人的 temperature 應為 0.7
    And 機器人的 max_tokens 應為 2048
