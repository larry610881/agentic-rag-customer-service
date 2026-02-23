Feature: LLM Provider Config
  多 Provider 設定：base_url 客製化與 API key 向下相容

  Scenario: OpenAILLMService 使用自訂 base_url
    Given 建立 OpenAILLMService 時指定 base_url 為 "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    Then 服務的 base_url 應為 "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

  Scenario: OpenAILLMService 預設 base_url
    Given 建立 OpenAILLMService 時未指定 base_url
    Then 服務的 base_url 應為 "https://api.openai.com/v1"

  Scenario: effective_openai_api_key 優先使用 openai_api_key
    Given Settings 設定 openai_api_key 為 "key-new" 且 openai_chat_api_key 為 "key-old"
    Then effective_openai_api_key 應為 "key-new"

  Scenario: effective_openai_api_key 回退到 openai_chat_api_key
    Given Settings 未設定 openai_api_key 且 openai_chat_api_key 為 "key-old"
    Then effective_openai_api_key 應為 "key-old"
