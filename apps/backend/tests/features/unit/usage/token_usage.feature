Feature: Token Usage 追蹤
  作為系統管理者
  我希望每次 LLM 呼叫都記錄 token 使用量
  以便追蹤成本與使用模式

  Scenario: RAG 查詢結果包含 token 使用量
    Given 知識庫已設定且有搜尋結果
    When 執行 RAG 查詢
    Then RAGResponse 應包含 usage 欄位
    And usage 的 model 應為 "fake"

  Scenario: FakeLLM 回傳零 usage
    Given 使用 FakeLLMService
    When 呼叫 generate 生成回答
    Then 回傳的 LLMResult 應包含 TokenUsage
    And usage 的 total_tokens 應為 0

  Scenario: TokenUsage 支援累加
    Given 兩個 TokenUsage 物件
    When 將兩個 usage 相加
    Then 結果的 input_tokens 應為兩者之和
    And 結果的 output_tokens 應為兩者之和
    And 結果的 estimated_cost 應為兩者之和
