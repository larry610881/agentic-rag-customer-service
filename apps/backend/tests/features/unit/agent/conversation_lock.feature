Feature: Conversation Lock — Reject concurrent requests
  Scenario: 第一個請求取得鎖並正常執行
    Given 一個空閒的 conversation
    When 使用者送出訊息
    Then 應成功取得鎖並執行 agent

  Scenario: 第二個請求被拒絕
    Given 一個正在處理中的 conversation
    When 同一使用者再次送出訊息
    Then 應回傳 busy_reply_message 而非執行 agent

  Scenario: Redis 斷線時降級為無鎖
    Given Redis 連線中斷
    When 使用者送出訊息
    Then 應正常執行 agent（降級無鎖）

  Scenario: Agent 執行完畢後鎖自動釋放
    Given 一個正在處理中的 conversation
    When agent 執行完畢
    Then 鎖應被釋放，下一個請求可取得
