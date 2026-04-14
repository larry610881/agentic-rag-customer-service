Feature: LLM Provider Config
  多 Provider 設定：base_url 客製化

  Scenario: OpenAILLMService 使用自訂 base_url
    Given 建立 OpenAILLMService 時指定 base_url 為 "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    Then 服務的 base_url 應為 "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

  Scenario: OpenAILLMService 預設 base_url
    Given 建立 OpenAILLMService 時未指定 base_url
    Then 服務的 base_url 應為 "https://api.openai.com/v1"
