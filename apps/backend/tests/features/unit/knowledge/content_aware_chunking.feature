Feature: Content-Aware Chunking
  根據 content_type 自動路由到對應的分塊策略

  Scenario: content_type 為 text/csv 時路由到 CSV 策略
    Given 一個 ContentAwareTextSplitterService 有 CSV 策略和 default 策略
    When 以 content_type "text/csv" 執行分塊
    Then CSV 策略被呼叫
    And default 策略未被呼叫

  Scenario: content_type 為 text/plain 時路由到 default 策略
    Given 一個 ContentAwareTextSplitterService 有 CSV 策略和 default 策略
    When 以 content_type "text/plain" 執行分塊
    Then default 策略被呼叫
    And CSV 策略未被呼叫

  Scenario: 未知 content_type 時 fallback 到 default 策略
    Given 一個 ContentAwareTextSplitterService 有 CSV 策略和 default 策略
    When 以 content_type "application/octet-stream" 執行分塊
    Then default 策略被呼叫
    And CSV 策略未被呼叫
