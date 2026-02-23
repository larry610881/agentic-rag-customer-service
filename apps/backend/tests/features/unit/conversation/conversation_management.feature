Feature: Conversation Management
  對話管理能建立對話並管理訊息

  Scenario: 建立新對話並新增使用者訊息
    Given 一個屬於 tenant "tenant-001" 的新對話
    When 新增一條使用者訊息 "你好，請問退貨政策？"
    Then 對話應包含 1 條訊息
    And 訊息角色應為 "user"

  Scenario: 對話訊息包含正確角色
    Given 一個屬於 tenant "tenant-001" 的新對話
    When 新增一條使用者訊息 "你好"
    And 新增一條助手訊息 "您好，很高興為您服務"
    Then 對話應包含 2 條訊息
    And 第 1 條訊息角色應為 "user"
    And 第 2 條訊息角色應為 "assistant"

  Scenario: 新增多條訊息後訊息列表正確排序
    Given 一個屬於 tenant "tenant-001" 的新對話
    When 依序新增 3 條訊息
    Then 對話應包含 3 條訊息
    And 訊息應按建立時間排序
