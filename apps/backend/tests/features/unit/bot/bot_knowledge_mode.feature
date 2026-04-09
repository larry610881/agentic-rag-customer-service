Feature: 機器人知識表徵模式（Knowledge Mode）
  作為系統管理員，我要能為每個機器人選擇使用 RAG 或 LLM Wiki 作為知識查詢策略，
  以便根據文件規模與問題型態挑選最適合的方案

  Scenario: 建立機器人預設為 RAG 模式
    Given 租戶 "t-001" 存在
    When 建立機器人名稱 "預設 Bot" 不指定知識模式
    Then 機器人應成功建立
    And 機器人的知識模式應為 "rag"

  Scenario: 建立機器人並指定為 Wiki 模式
    Given 租戶 "t-001" 存在
    When 建立機器人名稱 "Wiki Bot" 指定知識模式為 "wiki"
    Then 機器人應成功建立
    And 機器人的知識模式應為 "wiki"

  Scenario: 更新機器人知識模式從 RAG 改為 Wiki
    Given 租戶 "t-001" 已存在一個 RAG 模式的機器人
    When 將機器人的知識模式更新為 "wiki"
    Then 機器人的知識模式應為 "wiki"

  Scenario: 更新機器人知識模式從 Wiki 改回 RAG
    Given 租戶 "t-001" 已存在一個 Wiki 模式的機器人
    When 將機器人的知識模式更新為 "rag"
    Then 機器人的知識模式應為 "rag"

  Scenario: 未更新知識模式時不應變動原值
    Given 租戶 "t-001" 已存在一個 Wiki 模式的機器人
    When 只更新機器人的名稱為 "新名稱"
    Then 機器人的名稱應為 "新名稱"
    And 機器人的知識模式應為 "wiki"

  Scenario: 建立機器人時指定不支援的知識模式
    Given 租戶 "t-001" 存在
    When 嘗試建立機器人指定知識模式為 "invalid"
    Then 應回傳知識模式錯誤
