Feature: Bot LLM Provider/Model 欄位校驗 (Bot LLM Field Validation)
    身為租戶管理員
    我想要在建立或更新 Bot 時校驗 LLM 和 Eval 欄位
    以便防止無效的 provider/model 組合

    Scenario: 有效的 llm_provider 允許通過
        Given 一個建立 Bot 請求帶有 llm_provider "openai" 和 llm_model "gpt-4o"
        When 執行 LLM 欄位校驗
        Then 不應拋出異常

    Scenario: 無效的 llm_provider 回傳 400
        Given 一個建立 Bot 請求帶有 llm_provider "invalid_provider" 和 llm_model ""
        When 執行 LLM 欄位校驗
        Then 應拋出 400 錯誤包含 "llm_provider must be one of"

    Scenario: llm_model 設定但 llm_provider 為空回傳 400
        Given 一個建立 Bot 請求帶有 llm_provider "" 和 llm_model "gpt-4o"
        When 執行 LLM 欄位校驗
        Then 應拋出 400 錯誤包含 "llm_model requires llm_provider"

    Scenario: 空字串 provider 和 model 允許通過（使用系統預設）
        Given 一個建立 Bot 請求帶有 llm_provider "" 和 llm_model ""
        When 執行 LLM 欄位校驗
        Then 不應拋出異常

    Scenario: 無效的 eval_provider 回傳 400
        Given 一個建立 Bot 請求帶有 eval_provider "bad_provider" 和 eval_model ""
        When 執行 LLM 欄位校驗
        Then 應拋出 400 錯誤包含 "eval_provider must be one of"

    Scenario: eval_model 設定但 eval_provider 為空回傳 400
        Given 一個建立 Bot 請求帶有 eval_provider "" 和 eval_model "gemini-flash"
        When 執行 LLM 欄位校驗
        Then 應拋出 400 錯誤包含 "eval_model requires eval_provider"
