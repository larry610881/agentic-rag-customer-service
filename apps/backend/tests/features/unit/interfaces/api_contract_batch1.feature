Feature: API 契約改造第一批（Issue #97）
  日期單一 profile、錯誤 schema 進 OpenAPI、對外 router 穩定錯誤碼、
  可空集合語意寫進 schema、OpenAPI 由程式產出並提交、CORS expose 標頭。

  Scenario Outline: ApiDateTime 只輸出一種形狀（UTC、Z、固定三位小數）
    When 以 ApiDateTime 序列化 <input>
    Then 序列化結果為 "<output>"
    And 序列化結果符合 API_DATETIME_PATTERN

    Examples:
      | input                              | output                   |
      | 2026-09-16T10:00:00+00:00          | 2026-09-16T10:00:00.000Z |
      | 2026-09-16T10:00:00.123456+00:00   | 2026-09-16T10:00:00.123Z |
      | 2026-09-16T18:00:00.001+08:00      | 2026-09-16T10:00:00.001Z |
      | 2026-09-16T10:00:00 (naive)        | 2026-09-16T10:00:00.000Z |

  Scenario: ApiDateTime 的 JSON schema 帶 pattern
    When 取得含 ApiDateTime 欄位的模型 JSON schema
    Then 該欄位的 schema 含 format "date-time" 與 API_DATETIME_PATTERN

  Scenario: 全部回應模型的 datetime 欄位都改用 ApiDateTime
    When 掃描全部回應模型的 JSON schema
    Then 沒有任何 date-time 欄位缺少 API_DATETIME_PATTERN

  Scenario: 錯誤回應 schema 進 OpenAPI
    Given 一個宣告了 API_ERROR_RESPONSES 的測試應用
    When 取得該應用的 OpenAPI
    Then 端點的 401 與 404 回應引用 ErrorResponse
    And 端點的 422 回應引用 ValidationErrorResponse 而非 HTTPValidationError

  Scenario: 全部 router 不再有句子型 HTTPException
    When 掃描全部 router 原始碼
    Then 沒有任何 "raise HTTPException(" 出現

  Scenario: 程式裡每個 EntityNotFoundError 的 entity_type 都在 not_found 常數表
    When 掃描 src 內所有 EntityNotFoundError 的 entity_type 字面值
    Then 每一個都對應到 ENTITY_NOT_FOUND_CODES 的項目

  Scenario: 提交的 openapi.json 與程式產出一致
    When 以 create_app 產出 OpenAPI 並與 docs/api/openapi.json 比對
    Then 兩者完全相同

  Scenario: CORS 對瀏覽器 expose 重試與追蹤標頭
    When 帶 Origin 對 /api/v1/health 送 GET
    Then 回應的 Access-Control-Expose-Headers 含 "Retry-After"、"X-Request-ID"、"X-RateLimit-Remaining"、"Idempotent-Replayed"
