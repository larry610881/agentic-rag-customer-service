Feature: TeamSupervisor 團隊路由
  TeamSupervisor 接收 WorkerContext，依序詢問子 Worker 是否能處理，
  第一個回應 can_handle=True 的 Worker 負責處理。

  Scenario: 路由到第一個能處理的 Worker
    Given 團隊包含 WorkerA 和 WorkerB
    And WorkerA 能處理該訊息
    When TeamSupervisor 處理訊息 "我要退貨"
    Then 應由 WorkerA 回應
    And WorkerB 不應被呼叫

  Scenario: 跳過無法處理的 Worker
    Given 團隊包含 WorkerA 和 WorkerB
    And WorkerA 無法處理該訊息
    And WorkerB 能處理該訊息
    When TeamSupervisor 處理訊息 "查詢商品"
    Then 應由 WorkerB 回應

  Scenario: 所有 Worker 都無法處理時回傳預設訊息
    Given 團隊包含 WorkerA 和 WorkerB
    And WorkerA 無法處理該訊息
    And WorkerB 無法處理該訊息
    When TeamSupervisor 處理訊息 "隨機亂打"
    Then 應回傳無法處理的預設訊息
