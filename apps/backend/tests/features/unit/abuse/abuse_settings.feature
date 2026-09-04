Feature: 異常控管設定三層 (Abuse Settings: Platform / Profile / Tenant)
    身為系統管理員
    我要一份系統預設、幾個方案、再指定每個租戶用哪個方案或微調，而且只有我能改
    以便租戶管理員只看得到自己生效中的設定，不能把控管調到等於關閉

    # --- domain ---

    Scenario Outline: 覆寫必須在平台允許範圍內
        When 驗證覆寫 "<key>" 為 <value>
        Then 驗證結果為 <outcome>

        Examples:
            | key                   | value     | outcome |
            | mode                  | "monitor" | 通過    |
            | mode                  | "off"     | 失敗    |
            | threshold_l1          | 3         | 通過    |
            | threshold_l1          | 0         | 失敗    |
            | threshold_l3          | 999       | 失敗    |
            | duration_l3           | 600       | 通過    |
            | pacing_max_per_minute | 200       | 失敗    |
            | fail_open             | false     | 失敗    |
            | max_level_user        | 4         | 通過    |

    Scenario: 門檻必須遞增
        When 驗證覆寫組 threshold_l1 10 threshold_l2 5
        Then 驗證失敗訊息含 "increasing"

    Scenario: 預設 → 平台 → 方案 → 租戶微調的解析順序
        Given 平台覆寫 mode "monitor" threshold_l1 4
        And 租戶 "t1" 指定方案 "strict" 並微調 duration_l3 1200
        When 解析租戶 "t1" 的生效政策
        Then 生效政策 mode 為 "monitor"、threshold_l1 為 2、threshold_l3 為 10、duration_l3 為 1200

    Scenario: 未指定方案的租戶用 standard
        Given 平台覆寫 mode "monitor" threshold_l1 4
        When 解析租戶 "t9" 的生效政策
        Then 生效政策 mode 為 "monitor"、threshold_l1 為 4、threshold_l3 為 15、duration_l3 為 900

    # --- provider ---

    Scenario: 政策快取 60 秒，DB 失效時退回預設
        Given 設定儲存庫（會被讀取次數計數）與快取 provider
        When 連續讀取租戶 "t1" 的政策 3 次
        Then 儲存庫只被讀取 1 輪
        When 設定儲存庫失效並清除快取
        And 連續讀取租戶 "t1" 的政策 1 次
        Then 讀到的政策為預設 enforce

    # --- use cases ---

    Scenario: 更新租戶設定會驗方案、寫稽核並清快取
        Given 設定儲存庫（會被讀取次數計數）與快取 provider
        When 系統管理員把租戶 "t1" 設為方案 "strict" 並微調 mode "monitor"
        Then 儲存的租戶覆寫含 profile "strict" 與 mode "monitor"
        And 稽核應記錄 "abuse_settings" 的 "update"
        And 快取已清除

    Scenario: 指定不存在的方案被拒
        Given 設定儲存庫（會被讀取次數計數）與快取 provider
        When 系統管理員把租戶 "t1" 設為方案 "nope" 並微調 mode "monitor"
        Then 更新失敗訊息含 "Unknown profile"

    Scenario: 受控清單列出鎖定中的主體並遮罩
        Given 分數儲存中租戶 "t1" 的訪客 "visitor-abcdef-123456" 鎖定在等級 3
        And 分數儲存中租戶 "t2" 的訪客 "other" 鎖定在等級 2
        When 列出租戶 "t1" 的受控主體
        Then 受控清單有 1 筆，等級 3，遮罩為 "visi…56"

    # --- API 授權 ---

    Scenario Outline: 設定 API 只有系統管理員能寫，租戶管理員只能讀自己的
        Given 已啟動的異常控管設定測試應用
        And 以租戶 "<tenant>" 角色 "<role>" 的設定憑證
        When 請求設定端點 "<method>" "<path>"
        Then 設定端點回應狀態碼為 <status>

        Examples:
            | tenant | role         | method | path                                       | status |
            | SYSTEM | system_admin | GET    | /api/v1/admin/abuse/settings                | 200    |
            | t1     | tenant_admin | GET    | /api/v1/admin/abuse/settings                | 403    |
            | t1     | tenant_admin | GET    | /api/v1/admin/abuse/settings/tenants/t1     | 200    |
            | t1     | tenant_admin | GET    | /api/v1/admin/abuse/settings/tenants/t2     | 403    |
            | t1     | tenant_admin | PUT    | /api/v1/admin/abuse/settings/tenants/t1     | 403    |
            | SYSTEM | system_admin | PUT    | /api/v1/admin/abuse/settings/tenants/t1     | 200    |
            | SYSTEM | system_admin | PUT    | /api/v1/admin/abuse/settings/platform       | 200    |
            | t1     | user         | GET    | /api/v1/admin/abuse/controls                | 403    |
            | t1     | tenant_admin | GET    | /api/v1/admin/abuse/controls                | 200    |
            | t1     | tenant_admin | POST   | /api/v1/admin/abuse/controls/release        | 403    |
            | SYSTEM | system_admin | POST   | /api/v1/admin/abuse/controls/release        | 204    |

    Scenario: 租戶管理員看到的生效設定標示為不可編輯，受控清單不含完整 id
        Given 已啟動的異常控管設定測試應用
        And 以租戶 "t1" 角色 "tenant_admin" 的設定憑證
        And 分數儲存中租戶 "t1" 的訪客 "visitor-abcdef-123456" 鎖定在等級 3
        When 請求設定端點 "GET" "/api/v1/admin/abuse/settings/tenants/t1"
        Then 回應 editable 為 false
        When 請求設定端點 "GET" "/api/v1/admin/abuse/controls"
        Then 受控清單回應不含 "visitor-abcdef-123456" 且含 "visi…56"
