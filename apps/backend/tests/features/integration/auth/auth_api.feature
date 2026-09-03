Feature: Auth API Integration
  使用真實 DB 驗證認證 API 完整流程

  Scenario: 系統管理員成功建立使用者
    Given 已存在租戶 "Auth Corp"
    When 我以系統管理員送出 POST /api/v1/auth/register 帳號 "user@test.com" 密碼 "pass1234" 關聯該租戶
    Then 回應狀態碼為 201
    And 回應包含 email 為 "user@test.com"

  Scenario: 重複 email 註冊回傳 400
    Given 已存在租戶 "Auth Corp"
    And 已註冊使用者 "dup@test.com" 密碼 "pass1234" 關聯該租戶
    When 我以系統管理員送出 POST /api/v1/auth/register 帳號 "dup@test.com" 密碼 "pass1234" 關聯該租戶
    Then 回應狀態碼為 400

  Scenario: 無憑證註冊回傳 401（Issue #67）
    Given 已存在租戶 "Auth Corp"
    When 我無憑證送出 POST /api/v1/auth/register 帳號 "anon@test.com" 密碼 "pass1234" 關聯該租戶
    Then 回應狀態碼為 401

  Scenario: 一般使用者建立他人帳號回傳 403（Issue #67）
    Given 已存在租戶 "Auth Corp"
    When 我以該租戶一般使用者送出 POST /api/v1/auth/register 帳號 "peer@test.com" 密碼 "pass1234" 關聯該租戶
    Then 回應狀態碼為 403

  Scenario: 租戶管理員不得建立系統管理員（Issue #67）
    Given 已存在租戶 "Auth Corp"
    When 我以該租戶管理員送出 POST /api/v1/auth/register 角色 "system_admin" 帳號 "root@test.com" 密碼 "pass1234"
    Then 回應狀態碼為 403

  Scenario: 成功登入使用者
    Given 已存在租戶 "Auth Corp"
    And 已註冊使用者 "login@test.com" 密碼 "secret123" 關聯該租戶
    When 我送出 POST /api/v1/auth/login 帳號 "login@test.com" 密碼 "secret123"
    Then 回應狀態碼為 200
    And 回應包含 access_token

  Scenario: 錯誤密碼登入回傳 401
    Given 已存在租戶 "Auth Corp"
    And 已註冊使用者 "wrong@test.com" 密碼 "correct" 關聯該租戶
    When 我送出 POST /api/v1/auth/login 帳號 "wrong@test.com" 密碼 "incorrect"
    Then 回應狀態碼為 401

  Scenario: 不存在的帳號登入回傳 401
    When 我送出 POST /api/v1/auth/login 帳號 "nobody@test.com" 密碼 "whatever"
    Then 回應狀態碼為 401

  Scenario: 給 tenant_id 已換不到票（Issue #67）
    Given 已存在租戶 "Token Corp"
    When 我以該租戶 ID 送出 POST /api/v1/auth/token
    Then 回應狀態碼為 400

  Scenario: 租戶登入（legacy）
    Given 已存在租戶 "Legacy Corp"
    When 我送出 POST /api/v1/auth/login 帳號 "Legacy Corp" 密碼 "any"
    Then 回應狀態碼為 200
    And 回應包含 access_token

  Scenario: 不存在的租戶登入回傳 401
    When 我送出 POST /api/v1/auth/login 帳號 "NonExistent" 密碼 "any"
    Then 回應狀態碼為 401
