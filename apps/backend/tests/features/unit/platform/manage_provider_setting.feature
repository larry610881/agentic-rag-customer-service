Feature: Manage Provider Settings
  管理供應商設定的 CRUD 與連線測試

  Scenario: 建立時 API Key 應被加密
    Given 一個供應商設定建立用例
    When 我以明文 API Key "sk-plain-key" 建立 "llm" 類型的 "anthropic" 供應商
    Then 儲存的設定 API Key 應為加密值
    And 加密值不應等於 "sk-plain-key"

  Scenario: 更新 API Key 應重新加密
    Given 一個已存在的供應商設定，ID 為 "setting-001"
    When 我更新設定 "setting-001" 的 API Key 為 "sk-new-key"
    Then 儲存的設定 API Key 應為新的加密值

  Scenario: 列出所有 LLM 供應商
    Given 系統中有 2 個 LLM 供應商和 1 個 Embedding 供應商
    When 我列出所有 "llm" 類型的供應商
    Then 應回傳 2 個供應商設定

  Scenario: 刪除供應商
    Given 一個已存在的供應商設定，ID 為 "setting-del"
    When 我刪除設定 "setting-del"
    Then 刪除操作應成功

  Scenario: 測試供應商連線
    Given 一個已存在的 fake 供應商設定，ID 為 "setting-fake"
    When 我測試設定 "setting-fake" 的連線
    Then 連線測試結果應為成功
