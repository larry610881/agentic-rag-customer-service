Feature: 租戶 API key 端到端（真實 DB）
  使用真實 PostgreSQL 驗證：建立 key → client_credentials 換票 → 依 scope 存取 → 撤銷即失效

  Background:
    Given 已存在租戶 "Api Corp" 與其租戶管理員

  Scenario: 租戶管理員建立 key 並以 client_credentials 換票呼叫 API
    When 租戶管理員建立 API key 名稱 "看板" scopes "chat:history:read bots:read"
    Then 回應狀態碼為 201
    And 建立回應含一次性 client_secret
    When 以該 key 換票
    Then 回應狀態碼為 200
    When 以機器票送出 GET /api/v1/conversations
    Then 回應狀態碼為 200
    When 以機器票送出 GET /api/v1/knowledge-bases
    Then 回應狀態碼為 403
    When 以機器票送出 GET /api/v1/api-keys
    Then 回應狀態碼為 403

  Scenario: 撤銷後既有機器票立即失效且無法再換票
    When 租戶管理員建立 API key 名稱 "看板" scopes "bots:read"
    And 以該 key 換票
    And 租戶管理員撤銷該 key
    Then 回應狀態碼為 200
    When 以機器票送出 GET /api/v1/bots
    Then 回應狀態碼為 401
    When 以該 key 換票
    Then 回應狀態碼為 401

  Scenario: 其他租戶的管理員看不到也撤銷不了這把 key
    When 租戶管理員建立 API key 名稱 "看板" scopes "bots:read"
    And 另一租戶 "Other Corp" 的管理員列出 API key
    Then 回應狀態碼為 200
    And 列表不含該 key
    When 另一租戶 "Other Corp" 的管理員撤銷該 key
    Then 回應狀態碼為 404
