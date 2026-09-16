Feature: LINE 通路對等 — trace 持久化、攔截回應、長期記憶共用（Issue #99 二-2/3/6）
  web / widget / LINE 對同一件管線步驟只准有一份實作：
  trace 落庫、防護攔截回應組裝、記憶載入與萃取。

  Scenario: 共用的 trace 持久化寫入一列且帶 outcome
    Given 一個含 failed 節點的已完成 trace 與假的 session factory
    When 以 source "line" 呼叫 persist_finished_trace
    Then 寫入一列 agent_execution_traces，source 為 "line" 且 outcome 為 "failed"

  Scenario: 共用的攔截回應對 json bot 帶已解析物件
    Given 一個 output_format 為 json 的 OutputSpec 與被攔截的 guard 結果
    When 以 blocked_input_response 組回應
    Then 回應的 guard_blocked 為 "input"、answer 為 JSON 字串且 structured_output 為物件

  Scenario: LINE 對開啟記憶的 bot 載入記憶並注入提示
    Given 一個開啟記憶的 LINE bot 與會回傳記憶 "使用者偏好無糖飲品" 的記憶服務
    When LINE 用戶 "U-mem" 送出 "有什麼推薦"
    Then 傳給 agent 的 history_context 以 "使用者偏好無糖飲品" 開頭
    And 記憶服務以 source "line" 與 external_id "U-mem" 載入

  Scenario: LINE 對話達門檻後排程記憶萃取
    Given 一個開啟記憶且門檻為 1 的 LINE bot 與記憶服務
    When LINE 用戶 "U-mem" 送出 "有什麼推薦"
    Then 記憶服務收到一次萃取排程，source 為 "line"

  Scenario: LINE 未注入記憶服務時行為不變
    Given 一個開啟記憶的 LINE bot 但沒有記憶服務
    When LINE 用戶 "U-mem" 送出 "有什麼推薦"
    Then agent 正常被呼叫且沒有例外
