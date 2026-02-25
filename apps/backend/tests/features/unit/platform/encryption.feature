Feature: AES Encryption Service
  AES-256-GCM 加密 API Key

  Scenario: 加密後解密還原原始值
    Given 一個 AES 加密服務
    When 我加密 "sk-secret-key-12345"
    And 我解密加密後的結果
    Then 解密結果應為 "sk-secret-key-12345"

  Scenario: 加密結果每次不同
    Given 一個 AES 加密服務
    When 我加密 "same-key" 兩次
    Then 兩次加密結果應不同
