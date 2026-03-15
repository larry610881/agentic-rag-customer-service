Feature: 載入用戶記憶
  作為系統，需要載入訪客的長期記憶並格式化為 LLM 可用的 prompt

  Scenario: 有記憶時格式化為 prompt
    Given 訪客 Profile "p-001" 有 2 筆記憶事實
    When 載入 Profile "p-001" 的記憶
    Then 記憶 prompt 應包含 "偏好配送方式: 冷凍配送"
    And 記憶 prompt 應包含 "姓名: Alice"
    And 記憶 prompt 應以 "[用戶記憶]" 開頭

  Scenario: 無記憶時回傳空白 context
    Given 訪客 Profile "p-002" 沒有任何記憶
    When 載入 Profile "p-002" 的記憶
    Then 記憶 context 應為空
    And has_memory 應為 false

  Scenario: 過期記憶不載入
    Given 訪客 Profile "p-003" 有一筆已過期的記憶
    When 載入 Profile "p-003" 的記憶
    Then 記憶 context 應為空
