Feature: Admin User Management
  管理員使用者 CRUD 管理功能

  Background:
    Given 系統中有以下使用者:
      | email              | role         | tenant_id                            |
      | admin@example.com  | system_admin | 00000000-0000-0000-0000-000000000000 |
      | user1@example.com  | user         | tenant-001                           |
      | user2@example.com  | tenant_admin | tenant-002                           |

  # --- List Users ---

  Scenario: 列出所有使用者
    When 管理員列出所有使用者
    Then 應回傳 3 位使用者

  Scenario: 依租戶篩選使用者
    When 管理員列出租戶 "tenant-001" 的使用者
    Then 應回傳 1 位使用者

  # --- Update User ---

  Scenario: 更新使用者角色為 tenant_admin
    When 管理員將使用者 "user1@example.com" 的角色更新為 "tenant_admin"
    Then 使用者角色應更新為 "tenant_admin"

  Scenario: 更新使用者的租戶綁定
    When 管理員將使用者 "user1@example.com" 的租戶更新為 "tenant-999"
    Then 使用者租戶應更新為 "tenant-999"

  Scenario: 不可將非 system_admin 綁定到系統租戶
    When 管理員將使用者 "user1@example.com" 的租戶更新為 "00000000-0000-0000-0000-000000000000"
    Then 應拋出無效租戶綁定錯誤

  Scenario: 不可將 system_admin 綁定到非系統租戶
    When 管理員將使用者 "admin@example.com" 的角色更新為 "system_admin" 並租戶更新為 "tenant-001"
    Then 應拋出無效租戶綁定錯誤

  # --- Delete User ---

  Scenario: 刪除使用者
    When 管理員刪除使用者 "user1@example.com"
    Then 使用者應被刪除

  Scenario: 刪除不存在的使用者應拋出錯誤
    When 管理員刪除使用者 ID 為 "non-existent-id"
    Then 應拋出使用者不存在錯誤

  # --- Reset Password ---

  Scenario: 重設使用者密碼
    When 管理員重設使用者 "user1@example.com" 的密碼為 "newPass123"
    Then 使用者密碼應被更新
