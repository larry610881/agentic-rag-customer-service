Feature: Bot 管理完整流程
  E2E 驗證：建立 Bot → 綁定 KB → 更新設定 → 查詢列表 → 刪除

  Scenario: Bot 生命週期管理
    Given 已完成租戶設定並建立知識庫

    # Step 1: 建立 Bot 並綁定 KB
    When 我建立 Bot "客服助手" 綁定知識庫
    Then 回應狀態碼為 201
    And Bot 名稱為 "客服助手"
    And Bot 已綁定知識庫

    # Step 2: 查詢 Bot 列表
    When 我查詢 Bot 列表
    Then 回應狀態碼為 200
    And Bot 列表包含 1 個 Bot

    # Step 3: 更新 Bot 名稱
    When 我更新 Bot 名稱為 "進階客服"
    Then 回應狀態碼為 200
    And Bot 名稱為 "進階客服"

    # Step 4: 查詢單一 Bot
    When 我查詢該 Bot 詳情
    Then 回應狀態碼為 200
    And Bot 名稱為 "進階客服"

    # Step 5: 刪除 Bot
    When 我刪除該 Bot
    Then 回應狀態碼為 204

    # Step 6: 確認已刪除
    When 我查詢 Bot 列表
    Then 回應狀態碼為 200
    And Bot 列表包含 0 個 Bot
