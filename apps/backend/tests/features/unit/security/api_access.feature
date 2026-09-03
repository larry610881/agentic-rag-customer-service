Feature: API 模式（機器憑證）端點行為 (API Access Surface)
    身為外部串接系統
    我用 client_id + client_secret 換票後呼叫聊天 API
    以便只在授權的 scope 與 bot 範圍內存取，人類端點對機器票關閉

    Scenario: grant_type 不支援回 400
        Given 已啟動的 API 存取測試應用
        When 以 grant_type "password" 換票
        Then API 回應狀態碼為 400
        And API 回應 detail 為 "unsupported_grant_type"

    Scenario: 錯誤憑證換票回 401 invalid_client
        Given 已啟動的 API 存取測試應用
        When 以 client "k1" secret "wrong" 換票
        Then API 回應狀態碼為 401
        And API 回應 detail 為 "invalid_client"

    Scenario: 正確憑證換票取得 Bearer 票
        Given 已啟動的 API 存取測試應用
        When 以 client "k1" 正確 secret 換票
        Then API 回應狀態碼為 200
        And 換票回應 token_type 為 "Bearer" expires_in 為 900

    Scenario: 超出 key 範圍的 scope 回 403 invalid_scope
        Given 已啟動的 API 存取測試應用
        When 以 client "k1" 正確 secret 換票並要求 scope "kb:write"
        Then API 回應狀態碼為 403
        And API 回應 detail 為 "invalid_scope"

    Scenario Outline: 機器票依 scope 決定端點可用
        Given 已啟動的 API 存取測試應用
        And 持有 client "k1" 的 api_access 票 scopes "<scopes>"
        When 以機器票請求 "<method>" "<path>"
        Then API 回應狀態碼為 <status>

        Examples:
            | scopes            | method | path                          | status |
            | chat:send         | POST   | /api/v1/agent/chat            | 200    |
            | chat:stream       | POST   | /api/v1/agent/chat            | 403    |
            | chat:history:read | GET    | /api/v1/conversations         | 200    |
            | chat:send         | GET    | /api/v1/conversations         | 403    |
            | bots:read         | GET    | /api/v1/bots                  | 200    |
            | chat:send         | GET    | /api/v1/bots                  | 403    |
            | feedback:write    | POST   | /api/v1/feedback              | 201    |
            | chat:send         | GET    | /api/v1/knowledge-bases       | 403    |
            | chat:send         | POST   | /api/v1/api-keys              | 403    |
            | chat:send         | GET    | /api/v1/settings/providers    | 403    |

    Scenario Outline: 機器票綁 bot 範圍
        Given 已啟動的 API 存取測試應用
        And 持有 client "k1" 的 api_access 票 scopes "chat:send" bot_ids "<bot_ids>"
        When 以機器票對 bot "<bot_id>" 送出聊天
        Then API 回應狀態碼為 <status>

        Examples:
            | bot_ids | bot_id | status |
            | b1,b2   | b1     | 200    |
            | b1,b2   | b9     | 403    |
            | b1      | none   | 403    |
            | -       | b9     | 200    |

    Scenario: 已撤銷的 key 其既有票立即失效
        Given 已啟動的 API 存取測試應用
        And 持有 client "k1" 的 api_access 票 scopes "chat:send"
        And client "k1" 已被撤銷
        When 以機器票請求 "POST" "/api/v1/agent/chat"
        Then API 回應狀態碼為 401

    Scenario: 人類票不受 scope 限制
        Given 已啟動的 API 存取測試應用
        And 持有租戶 "t1" 的一般使用者票
        When 以機器票請求 "GET" "/api/v1/conversations"
        Then API 回應狀態碼為 200

    Scenario Outline: API key 管理端點依角色授權
        Given 已啟動的 API 存取測試應用
        And 持有租戶 "<tenant>" 角色 "<role>" 的人類票
        When 以人類票建立租戶 "<target>" 的 API key
        Then API 回應狀態碼為 <status>

        Examples:
            | tenant | role         | target | status |
            | t1     | user         | t1     | 403    |
            | t1     | tenant_admin | t1     | 201    |
            | t1     | tenant_admin | t2     | 403    |
            | SYSTEM | system_admin | t2     | 201    |
            | SYSTEM | system_admin | -      | 422    |

    Scenario: 建立回應含一次性的 client_secret，列表不含
        Given 已啟動的 API 存取測試應用
        And 持有租戶 "t1" 角色 "tenant_admin" 的人類票
        When 以人類票建立租戶 "t1" 的 API key
        Then API 回應狀態碼為 201
        And 建立回應含 client_secret
        When 以人類票列出 API key
        Then 列表回應每筆都不含 client_secret
