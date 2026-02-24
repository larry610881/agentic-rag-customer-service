Feature: Conversation History Strategy
  對話歷史處理策略 — 支援多種策略切換

  Scenario: Full 策略傳送全部歷史
    Given 一段包含 6 條訊息的對話歷史
    When 使用 full 策略處理歷史
    Then respond_context 應包含全部 6 條訊息
    And strategy_name 應為 "full"

  Scenario: SlidingWindow 策略只保留最近 N 條
    Given 一段包含 20 條訊息的對話歷史
    When 使用 sliding_window 策略處理歷史且 history_limit 為 6
    Then respond_context 應僅包含最後 6 條訊息
    And strategy_name 應為 "sliding_window"

  Scenario: SummaryRecent 策略摘要舊對話並保留最近完整訊息
    Given 一段包含 10 條訊息的對話歷史
    When 使用 summary_recent 策略處理歷史且 recent_turns 為 2
    Then respond_context 應包含對話摘要標記
    And respond_context 應包含最近 4 條完整訊息
    And strategy_name 應為 "summary_recent"

  Scenario: 空歷史回傳空上下文
    Given 一段空的對話歷史
    When 使用 sliding_window 策略處理歷史
    Then respond_context 應為空字串
    And message_count 應為 0

  Scenario: SendMessageUseCase 透過策略傳遞 history_context 給 AgentService
    Given 一個注入 sliding_window 策略的 SendMessageUseCase
    And 一段包含歷史訊息的對話
    When 使用者在該對話發送新訊息
    Then AgentService 應收到非空的 history_context
    And AgentService 應收到非空的 router_context
