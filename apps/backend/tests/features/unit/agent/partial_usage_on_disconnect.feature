Feature: 生成中斷線的部分計費（Issue #99 一-2）
  客戶端在 LLM 生成中斷線時，供應商已對已生成的部分計費；平台沒有 usage 數字，
  改以已串出文字與提示估算 token 並標記 estimated，讓帳務不漏。

  Scenario: 生成中取消時以估算 usage 記帳並標記 estimated
    Given 一個會串出 token 與 usage 的 kb bot 並注入估算器
    When 以 web 串流送出訊息並在第一個 token 後斷線
    Then record_usage 被呼叫 1 次
    And 記帳的 usage 標記 estimated 且 output_tokens 大於 0 且 input_tokens 大於 0
    And 對話未儲存
    And 只發生取消，沒有其他例外

  Scenario: 生成中取消但尚未串出任何字時不記帳
    Given 一個會串出 token 與 usage 的 kb bot 並注入估算器
    When 以 web 串流送出訊息並在生成開始前斷線
    Then record_usage 被呼叫 0 次
    And 只發生取消，沒有其他例外

  Scenario: 估算記帳失敗不影響取消流程
    Given 一個會串出 token 與 usage 的 kb bot 並注入估算器
    And record_usage 會拋例外
    When 以 web 串流送出訊息並在第一個 token 後斷線
    Then 只發生取消，沒有其他例外

  Scenario: estimated 旗標一路傳到 UsageRecord
    Given 一個 RecordUsageUseCase 與記憶體 usage repository
    When 以 estimated 的 TokenUsage 記帳
    Then 儲存的 UsageRecord 標記 estimated
