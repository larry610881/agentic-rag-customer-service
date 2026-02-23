Feature: MetaSupervisor 角色路由
  MetaSupervisor 依據 WorkerContext.user_role 路由到對應的 TeamSupervisor。
  支援 customer、marketing、executive 三種角色。

  Scenario: customer 角色路由到 CustomerTeamSupervisor
    Given MetaSupervisor 已註冊 customer 和 marketing 團隊
    And 使用者角色為 "customer"
    When MetaSupervisor 處理訊息 "我要查訂單"
    Then 應由 customer 團隊處理
    And 回應中應包含 conversation_id

  Scenario: marketing 角色路由到 MarketingTeamSupervisor
    Given MetaSupervisor 已註冊 customer 和 marketing 團隊
    And 使用者角色為 "marketing"
    When MetaSupervisor 處理訊息 "建立行銷活動"
    Then 應由 marketing 團隊處理

  Scenario: 未知角色使用 customer 作為預設
    Given MetaSupervisor 已註冊 customer 和 marketing 團隊
    And 使用者角色為 "unknown_role"
    When MetaSupervisor 處理訊息 "你好"
    Then 應由 customer 團隊處理

  Scenario: MetaSupervisor 整合情緒偵測
    Given MetaSupervisor 已註冊 customer 和 marketing 團隊
    And 使用者角色為 "customer"
    And 情緒服務已啟用
    When MetaSupervisor 處理包含負面情緒的訊息 "我非常不滿意這個服務"
    Then 回應應包含 sentiment 為 "negative"
    And 回應應標記為需要升級
