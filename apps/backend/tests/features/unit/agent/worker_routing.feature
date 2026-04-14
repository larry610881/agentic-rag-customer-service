Feature: Worker 路由分類
  作為系統，我需要用 LLM 將使用者訊息分類到對應的 Worker

  Scenario: 訊息命中 Worker 時回傳對應 WorkerConfig
    Given IntentClassifier 已初始化
    And 有 2 個 Workers 分別為 "客訴" 和 "商品查詢"
    When LLM 回傳分類結果 "客訴"
    Then 應回傳名為 "客訴" 的 WorkerConfig

  Scenario: 訊息未命中任何 Worker 時回傳 None
    Given IntentClassifier 已初始化
    And 有 2 個 Workers 分別為 "客訴" 和 "商品查詢"
    When LLM 回傳分類結果 "NONE"
    Then 應回傳 None

  Scenario: 無 Workers 時直接回傳 None 不呼叫 LLM
    Given IntentClassifier 已初始化
    When 以空的 Workers 清單分類
    Then 應回傳 None
    And LLM 不應被呼叫

  Scenario: LLM 呼叫失敗時 graceful fallback
    Given IntentClassifier 已初始化
    And 有 1 個 Worker 名為 "客訴"
    When LLM 呼叫拋出例外
    Then 應回傳 None
