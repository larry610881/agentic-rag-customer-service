Feature: Message Structured Content 持久化
  Tool 產生的 rich payload（contact / sources）應存入 structured_content，
  讓 Web Bot 重新載入歷史對話時能還原顯示

  Scenario: Tool 產生 contact payload 時存入 structured_content
    Given 一個會回傳 contact 的 Agent Service
    When 使用者發送訊息 "我要找真人客服"
    Then 助理訊息的 structured_content 應包含 contact 欄位

  Scenario: Tool 產生 sources 時併入 structured_content
    Given 一個回傳來源引用的 Agent Service
    When 使用者發送訊息 "查詢退貨政策"
    Then 助理訊息的 structured_content 應包含 sources 列表

  Scenario: 無 rich content 時 structured_content 為 None
    Given 一個只回傳純文字的 Agent Service
    When 使用者發送訊息 "你好"
    Then 助理訊息的 structured_content 應為 None

  # Streaming 路徑（execute_stream）：BUG-01 原實作在此路徑聚合 contact event
  Scenario: Streaming 過程 yield contact event 時聚合至 structured_content
    Given 一個會在 streaming 中 yield contact event 的 Agent Service
    When 使用者以 streaming 模式發送訊息 "我要找真人客服"
    Then streaming 助理訊息的 structured_content 應包含 contact 欄位

  Scenario: Streaming 過程 yield sources event 時併入 structured_content
    Given 一個會在 streaming 中 yield sources event 的 Agent Service
    When 使用者以 streaming 模式發送訊息 "查詢退貨政策"
    Then streaming 助理訊息的 structured_content 應包含 sources 列表
