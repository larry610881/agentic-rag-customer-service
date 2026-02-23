Feature: LLM Service
  LLM 服務能根據 context 生成回答並支援 streaming

  Scenario: FakeLLMService 回傳包含 context 的回答
    Given 一段 context 內容 "退貨政策：30天內可退貨"
    When 使用 FakeLLMService 生成回答
    Then 回答應包含 "根據知識庫"

  Scenario: FakeLLMService streaming 回傳多個 chunks
    Given 一段 context 內容 "退貨政策：30天內可退貨"
    When 使用 FakeLLMService streaming 生成回答
    Then 應收到多個 token chunks
    And 所有 chunks 組合後應包含 "根據知識庫"

  Scenario: 無 context 時回傳無相關資訊提示
    Given 空的 context 內容
    When 使用 FakeLLMService 生成回答
    Then 回答應包含 "沒有找到相關資訊"
