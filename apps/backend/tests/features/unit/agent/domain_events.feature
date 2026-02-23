Feature: Domain Events 基礎設施
  DomainEvent 基類與 EventBus 提供跨限界上下文的異步通信機制。

  Scenario: 建立 DomainEvent 自動產生 event_id 與時戳
    Given 建立一個 OrderRefunded 事件
    Then 事件應有非空的 event_id
    And 事件應有 occurred_at 時戳
    And tenant_id 應為指定值

  Scenario: EventBus 發佈事件觸發訂閱者
    Given EventBus 已訂閱 OrderRefunded 事件的處理器
    When 發佈一個 OrderRefunded 事件
    Then 訂閱的處理器應被呼叫一次
    And 處理器收到的事件應包含正確的 order_id

  Scenario: EventBus 多個訂閱者同時收到事件
    Given EventBus 已訂閱兩個 OrderRefunded 事件的處理器
    When 發佈一個 OrderRefunded 事件
    Then 兩個處理器都應被呼叫

  Scenario: EventBus 不同事件類型獨立處理
    Given EventBus 已訂閱 OrderRefunded 和 NegativeSentimentDetected 處理器
    When 發佈一個 OrderRefunded 事件
    Then OrderRefunded 處理器應被呼叫
    And NegativeSentimentDetected 處理器不應被呼叫
