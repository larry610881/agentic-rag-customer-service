Feature: 使用者登入 (User Login)
  作為電商平台使用者
  我希望能夠登入系統
  以便使用 AI 客服和知識庫管理功能

  Scenario: 成功登入並導向聊天頁
    Given 使用者在登入頁面
    When 使用者輸入帳號 "Demo Store"
    And 使用者輸入密碼 "password123"
    And 使用者點擊登入按鈕
    Then 應導向聊天頁面
    And 應顯示目前租戶名稱 "Demo Store"

  Scenario: 空白欄位顯示驗證錯誤
    Given 使用者在登入頁面
    When 使用者點擊登入按鈕
    Then 應顯示帳號欄位驗證錯誤 "Username is required"
    And 應顯示密碼欄位驗證錯誤 "Password is required"

  Scenario: 錯誤帳號顯示失敗訊息
    Given 使用者在登入頁面
    When 使用者輸入帳號 "NonExistentTenant"
    And 使用者輸入密碼 "wrongpassword"
    And 使用者點擊登入按鈕
    Then 應顯示登入失敗訊息 "Login failed. Please check your credentials."
