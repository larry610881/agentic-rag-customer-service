Feature: /agent/chat 對外契約加固（Issue #94）
  第三方（原生 app、展場測試機）接入 /api/v1/agent/chat 時，
  回應與錯誤形狀必須在所有路徑只有一種型別，且識別碼被替換時要有旗標。

  Scenario: 未帶 conversation_id 時回應標記為新建對話
    Given 一個回傳對話 id "conv-new" 的 SendMessage use case
    When 以不帶 conversation_id 的請求呼叫 agent_chat
    Then 回應的 conversation_created 為 true
    And 回應的 conversation_id 為 "conv-new"

  Scenario: 帶入的 conversation_id 被沿用時旗標為 false
    Given 一個回傳對話 id "conv-1" 的 SendMessage use case
    When 以 conversation_id "conv-1" 的請求呼叫 agent_chat
    Then 回應的 conversation_created 為 false

  Scenario: 帶入的 conversation_id 查不到或歸屬不符時旗標為 true
    Given 一個回傳對話 id "conv-platform" 的 SendMessage use case
    When 以 conversation_id "fab:user-42" 的請求呼叫 agent_chat
    Then 回應的 conversation_created 為 true
    And 回應的 conversation_id 為 "conv-platform"

  Scenario: SSE 的 conversation_id 事件同樣帶 conversation_created
    When 把請求端 conversation_id "conv-1" 套用到平台回傳 "conv-1" 的 conversation_id 事件
    Then 該事件的 conversation_created 為 false
    When 把請求端 conversation_id "conv-1" 套用到平台回傳 "conv-2" 的 conversation_id 事件
    Then 該事件的 conversation_created 為 true

  Scenario: JSON bot 的已解析物件放在 structured_content.output
    Given 一個回傳結構化輸出 {"status": "km", "category": "marketing", "answer": "特價 199 元"} 的 SendMessage use case
    When 以不帶 conversation_id 的請求呼叫 agent_chat
    Then 回應的 structured_content.output 等於該物件
    And 回應的 structured_content.sources 為空陣列
    And 回應的 answer 仍為字串

  Scenario: 只有聯絡按鈕時 structured_content.sources 仍為空陣列而非 null
    Given 一個回傳聯絡按鈕 {"label": "客服", "url": "tel:0800", "type": "phone"} 的 SendMessage use case
    When 以不帶 conversation_id 的請求呼叫 agent_chat
    Then 回應的 structured_content.sources 為空陣列
    And 回應的 structured_content.contact.label 為 "客服"

  Scenario: 純文字回覆且無附加內容時 structured_content 為 null
    Given 一個回傳純文字的 SendMessage use case
    When 以不帶 conversation_id 的請求呼叫 agent_chat
    Then 回應的 structured_content 為 null

  Scenario Outline: 所有 HTTP 錯誤 body 都有字串 detail、穩定 code 與 request_id
    Given 一個安裝了統一錯誤處理的測試應用
    When 對 "<path>" 送出 <method> 請求
    Then 狀態碼為 <status>
    And 錯誤 body 的 detail 是字串
    And 錯誤 body 的 code 為 "<code>"
    And 錯誤 body 的 request_id 與回應標頭 X-Request-ID 相同

    Examples:
      | path              | method | status | code               |
      | /missing-token    | GET    | 401    | token_missing      |
      | /snake-detail     | GET    | 403    | insufficient_scope |
      | /api-error        | GET    | 401    | token_expired      |
      | /sentence-detail  | GET    | 409    | conflict           |
      | /validate         | POST   | 422    | validation_error   |

  Scenario: 422 另附 errors 陣列保留欄位層級細節
    Given 一個安裝了統一錯誤處理的測試應用
    When 對 "/validate" 送出 POST 請求
    Then 狀態碼為 422
    And 錯誤 body 的 errors 是非空陣列且第一筆 loc 包含 "message"

  Scenario: 過期的 JWT 產生可辨識的 TokenExpiredError
    Given 一個以密鑰 "unit-secret" 建立的 JWTService
    When 解碼一個已過期的 access token
    Then 拋出 TokenExpiredError
