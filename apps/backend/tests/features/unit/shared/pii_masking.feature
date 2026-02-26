Feature: PII 遮蔽擴充 (PII Masking Expansion)

  Scenario: 信用卡號被遮蔽
    Given 文本包含信用卡號 "我的卡號是 4111-1111-1111-1111 請查詢"
    When 執行 PII 遮蔽
    Then 文本不應包含信用卡號
    And 信用卡號應被替換為 "****-****-****-****"

  Scenario: 台灣身分證字號被遮蔽
    Given 文本包含身分證字號 "身分證字號 A123456789 謝謝"
    When 執行 PII 遮蔽
    Then 文本不應包含身分證字號
    And 身分證字號應被替換為 "A1***"

  Scenario: IP 位址被遮蔽
    Given 文本包含 IP 位址 "來自 192.168.1.100 的請求"
    When 執行 PII 遮蔽
    Then 文本不應包含 IP 位址
    And IP 位址應被替換為 "***.***.***.***"
