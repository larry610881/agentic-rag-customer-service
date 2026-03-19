Feature: Widget 聊天 API 驗證
  作為外部網站，透過 Widget API 與機器人對話前，需通過安全驗證

  Background:
    Given 租戶 "t-001" 存在
    And 機器人 "bot-001" 屬於租戶 "t-001" short_code 為 "ab3Kx9"

  Scenario: Widget 啟用且來源合法時成功串流回應
    Given 機器人已啟用 widget 功能
    And 允許來源為 "https://shop.example.com"
    When 從來源 "https://shop.example.com" 發送 widget 訊息 "你好"
    Then 應成功回傳串流回應
    And 串流中應包含 conversation_id

  Scenario: Widget 未啟用時回傳 403
    Given 機器人未啟用 widget 功能
    When 從來源 "https://shop.example.com" 發送 widget 訊息 "你好"
    Then 應回傳錯誤碼 403
    And 錯誤訊息應包含 "Widget is not enabled"

  Scenario: 機器人停用時回傳 403
    Given 機器人已停用
    And 機器人已啟用 widget 功能
    When 從來源 "https://shop.example.com" 發送 widget 訊息 "你好"
    Then 應回傳錯誤碼 403
    And 錯誤訊息應包含 "Bot is not active"

  Scenario: 來源不在白名單時回傳 403
    Given 機器人已啟用 widget 功能
    And 允許來源為 "https://shop.example.com"
    When 從來源 "https://evil.com" 發送 widget 訊息 "你好"
    Then 應回傳錯誤碼 403
    And 錯誤訊息應包含 "Origin not allowed"

  Scenario: 機器人不存在時回傳 404
    When 以不存在的 short_code "nonexist" 從來源 "https://shop.example.com" 發送 widget 訊息
    Then 應回傳錯誤碼 404

  Scenario: keep_history 為 false 時不回傳 conversation_id
    Given 機器人已啟用 widget 功能
    And 允許來源為 "https://shop.example.com"
    And 機器人 widget_keep_history 設為 false
    When 從來源 "https://shop.example.com" 發送 widget 訊息 "你好"
    Then 應成功回傳串流回應
    And 串流中不應包含 conversation_id

  Scenario: keep_history 為 true 時回傳 conversation_id 可連續對話
    Given 機器人已啟用 widget 功能
    And 允許來源為 "https://shop.example.com"
    And 機器人 widget_keep_history 設為 true
    When 從來源 "https://shop.example.com" 發送 widget 訊息 "你好"
    Then 應成功回傳串流回應
    And 串流中應包含 conversation_id
