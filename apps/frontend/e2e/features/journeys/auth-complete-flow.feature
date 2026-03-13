Feature: 認證流程完整驗證
  作為平台使用者
  我希望登入系統並獲得正確的存取權限
  以便安全地使用平台功能

  Scenario: 空白欄位顯示驗證錯誤
    Given 使用者在登入頁面
    When 使用者點擊登入按鈕
    Then 應顯示帳號欄位驗證錯誤 "請輸入帳號"
    And 應顯示密碼欄位驗證錯誤 "請輸入密碼"

  Scenario: 錯誤憑證顯示失敗訊息
    Given 使用者在登入頁面
    When 使用者輸入帳號 "NonExistentTenant"
    And 使用者輸入密碼 "wrongpassword"
    And 使用者點擊登入按鈕
    Then 應顯示登入失敗訊息 "登入失敗，請確認帳號密碼是否正確。"

  Scenario: 系統管理員成功登入
    Given 使用者在登入頁面
    When 使用者輸入帳號 "Demo Store"
    And 使用者輸入密碼 "password123"
    And 使用者點擊登入按鈕
    Then 應導向聊天頁面

  Scenario: 租戶管理員成功登入
    Given 租戶管理員已登入
    Then 應導向聊天頁面
