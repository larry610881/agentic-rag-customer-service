Feature: Streaming 錯誤處理
  確保 streaming 過程中的異常回傳友善錯誤訊息

  Scenario: LLM 429 Rate Limit 回傳友善提示
    Given 一個會拋出 HTTP 429 錯誤的 LLM
    When 以 streaming 模式處理訊息
    Then 應收到 error 事件訊息為 "API 額度已用完，請稍後再試"
    And 最後一個事件應為 done

  Scenario: LLM 500 錯誤回傳通用訊息
    Given 一個會拋出 HTTP 500 錯誤的 LLM
    When 以 streaming 模式處理訊息
    Then 應收到 error 事件包含 "LLM 服務異常"

  Scenario: 未知異常不洩漏堆疊資訊
    Given 一個會拋出 RuntimeError 的 LLM
    When 以 streaming 模式處理訊息
    Then 應收到 error 事件訊息為 "處理訊息時發生錯誤，請重試"
    And error 訊息不應包含 "Traceback"
