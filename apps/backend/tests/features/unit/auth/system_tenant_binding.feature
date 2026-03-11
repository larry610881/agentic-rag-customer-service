Feature: 系統租戶綁定與權限守衛 (System Tenant Binding & Auth Guards)
    身為系統管理員
    我想要透過角色控制 API 存取權限
    以便保護敏感操作（租戶管理、日誌查看）

    Scenario: system_admin 可列出所有租戶
        Given 目前使用者角色為 "system_admin"
        When 我列出所有租戶
        Then 應回傳所有租戶列表

    Scenario: tenant_admin 只能看到自己的租戶
        Given 目前使用者角色為 "tenant_admin" 且 tenant_id 為 "t-001"
        When 我列出所有租戶
        Then 應只回傳 tenant_id 為 "t-001" 的租戶

    Scenario: 非 system_admin 不可建立租戶
        Given 目前使用者角色為 "tenant_admin"
        When 我嘗試建立租戶
        Then 應被拒絕並回傳 403

    Scenario: 非 system_admin 不可修改租戶
        Given 目前使用者角色為 "tenant_admin"
        When 我嘗試修改租戶 agent modes
        Then 應被拒絕並回傳 403

    Scenario: SYSTEM_TENANT_ID 常數已定義
        Then SYSTEM_TENANT_ID 應為 "00000000-0000-0000-0000-000000000000"
        And SYSTEM_TENANT_NAME 應為 "系統"
