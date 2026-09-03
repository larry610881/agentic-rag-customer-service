Feature: 認證面加固 P1 (Auth Surface Hardening)
    身為平台資安負責人
    我想要註冊、開發用發票、供應商設定、MCP 註冊表四個入口都受到認證與角色授權
    以便 POC 對外開放後，沒有人能自註冊成管理員、免憑證取票、或讀寫平台層設定

    # --- 註冊授權（domain policy）---

    Scenario Outline: 註冊授權政策依呼叫者角色與租戶判定
        Given 呼叫者角色 "<actor_role>" 租戶 "<actor_tenant>"
        When 檢查是否可建立角色 "<target_role>" 租戶 "<target_tenant>" 的使用者
        Then 授權結果應為 <allowed>

        Examples:
            | actor_role   | actor_tenant | target_role  | target_tenant | allowed |
            | system_admin | SYSTEM       | system_admin | SYSTEM        | True    |
            | system_admin | SYSTEM       | tenant_admin | t1            | True    |
            | tenant_admin | t1           | user         | t1            | True    |
            | tenant_admin | t1           | tenant_admin | t1            | True    |
            | tenant_admin | t1           | user         | t2            | False   |
            | tenant_admin | t1           | system_admin | SYSTEM        | False   |
            | tenant_admin | none         | user         | t1            | False   |
            | user         | t1           | user         | t1            | False   |
            | none         | t1           | user         | t1            | False   |

    # --- 註冊端點 ---

    Scenario: 無憑證註冊回傳 401
        Given 已啟動的測試應用
        When 無憑證送出註冊角色 "user" 租戶 "t1"
        Then 回應狀態碼為 401
        And 註冊用例不應被呼叫

    Scenario Outline: 註冊端點依呼叫者角色回應
        Given 已啟動的測試應用
        And 以角色 "<actor_role>" 租戶 "<actor_tenant>" 的憑證
        When 送出註冊角色 "<target_role>" 租戶 "<target_tenant>"
        Then 回應狀態碼為 <status>

        Examples:
            | actor_role   | actor_tenant | target_role  | target_tenant | status |
            | user         | t1           | user         | t1            | 403    |
            | legacy       | t1           | tenant_admin | t1            | 403    |
            | tenant_admin | t1           | user         | t2            | 403    |
            | tenant_admin | t1           | system_admin | SYSTEM        | 403    |
            | tenant_admin | t1           | user         | t1            | 201    |
            | system_admin | SYSTEM       | system_admin | SYSTEM        | 201    |

    Scenario: 註冊未知角色回傳 422
        Given 已啟動的測試應用
        And 以角色 "system_admin" 租戶 "SYSTEM" 的憑證
        When 送出註冊角色 "root" 租戶 "t1"
        Then 回應狀態碼為 422
        And 註冊用例不應被呼叫

    # --- 供應商設定 router ---

    Scenario Outline: 供應商設定端點需要認證
        Given 已啟動的測試應用
        When 無憑證請求 "<method>" "<path>"
        Then 回應狀態碼為 401

        Examples:
            | method | path                                          |
            | GET    | /api/v1/settings/providers                    |
            | POST   | /api/v1/settings/providers                    |
            | GET    | /api/v1/settings/providers/enabled-models     |
            | GET    | /api/v1/settings/providers/model-registry     |
            | GET    | /api/v1/settings/providers/abc                |
            | PUT    | /api/v1/settings/providers/abc                |
            | DELETE | /api/v1/settings/providers/abc                |
            | POST   | /api/v1/settings/providers/abc/test-connection|

    Scenario Outline: 供應商設定寫入與讀取只開放系統管理員
        Given 已啟動的測試應用
        And 以角色 "<role>" 租戶 "t1" 的憑證
        When 請求 "<method>" "<path>"
        Then 回應狀態碼為 <status>

        Examples:
            | role         | method | path                                           | status |
            | user         | GET    | /api/v1/settings/providers                     | 403    |
            | tenant_admin | GET    | /api/v1/settings/providers                     | 403    |
            | tenant_admin | POST   | /api/v1/settings/providers                     | 403    |
            | tenant_admin | DELETE | /api/v1/settings/providers/abc                 | 403    |
            | tenant_admin | POST   | /api/v1/settings/providers/abc/test-connection | 403    |
            | user         | GET    | /api/v1/settings/providers/enabled-models      | 200    |
            | user         | GET    | /api/v1/settings/providers/model-registry      | 200    |
            | system_admin | GET    | /api/v1/settings/providers                     | 200    |

    # --- MCP 註冊表 router ---

    Scenario Outline: MCP 註冊表端點需要認證
        Given 已啟動的測試應用
        When 無憑證請求 "<method>" "<path>"
        Then 回應狀態碼為 401

        Examples:
            | method | path                                  |
            | GET    | /api/v1/mcp-servers                   |
            | POST   | /api/v1/mcp-servers                   |
            | GET    | /api/v1/mcp-servers/abc               |
            | PUT    | /api/v1/mcp-servers/abc               |
            | DELETE | /api/v1/mcp-servers/abc               |
            | POST   | /api/v1/mcp-servers/discover          |
            | POST   | /api/v1/mcp-servers/abc/test-connection |

    Scenario Outline: MCP 註冊表寫入只開放系統管理員
        Given 已啟動的測試應用
        And 以角色 "tenant_admin" 租戶 "t1" 的憑證
        When 請求 "<method>" "<path>"
        Then 回應狀態碼為 403

        Examples:
            | method | path                                    |
            | POST   | /api/v1/mcp-servers                     |
            | PUT    | /api/v1/mcp-servers/abc                 |
            | DELETE | /api/v1/mcp-servers/abc                 |
            | POST   | /api/v1/mcp-servers/discover            |
            | POST   | /api/v1/mcp-servers/abc/test-connection |

    Scenario: 非管理員列出 MCP 伺服器一律以票內租戶查詢並忽略 query 參數
        Given 已啟動的測試應用
        And 以角色 "user" 租戶 "t1" 的憑證
        When 請求 "GET" "/api/v1/mcp-servers?tenant_id=t2"
        Then 回應狀態碼為 200
        And MCP 儲存庫應以租戶 "t1" 查詢可用清單

    Scenario: 系統管理員不帶 tenant_id 列出全部 MCP 伺服器
        Given 已啟動的測試應用
        And 以角色 "system_admin" 租戶 "SYSTEM" 的憑證
        When 請求 "GET" "/api/v1/mcp-servers"
        Then 回應狀態碼為 200
        And MCP 儲存庫應查詢全部清單

    Scenario Outline: 非管理員只能讀取自己可用的 MCP 伺服器
        Given 已啟動的測試應用
        And 以角色 "user" 租戶 "t1" 的憑證
        And MCP 伺服器 "abc" scope "<scope>" 租戶 "<tenants>" 啟用 <enabled>
        When 請求 "GET" "/api/v1/mcp-servers/abc"
        Then 回應狀態碼為 <status>

        Examples:
            | scope  | tenants | enabled | status |
            | global | -       | True    | 200    |
            | tenant | t1,t9   | True    | 200    |
            | tenant | t2      | True    | 404    |
            | global | -       | False   | 404    |
