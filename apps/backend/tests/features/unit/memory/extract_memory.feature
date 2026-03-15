Feature: 萃取對話記憶
  作為系統，需要從對話中萃取用戶事實並儲存為長期記憶

  Scenario: 成功從對話中萃取事實
    Given 訪客 Profile "p-001" 沒有既有記憶
    And LLM 萃取服務會回傳 2 筆事實
    When 萃取對話記憶
    Then 應 upsert 2 筆記憶事實

  Scenario: 無新事實時不寫入
    Given 訪客 Profile "p-001" 沒有既有記憶
    And LLM 萃取服務回傳空陣列
    When 萃取對話記憶
    Then 應 upsert 0 筆記憶事實

  Scenario: 相同 key 更新既有事實
    Given 訪客 Profile "p-001" 已有記憶 key "偏好配送方式" value "常溫配送"
    And LLM 萃取服務會回傳偏好配送方式為冷凍配送
    When 萃取對話記憶
    Then 應 upsert 1 筆記憶事實
    And 記憶 "偏好配送方式" 的值應為 "冷凍配送"
